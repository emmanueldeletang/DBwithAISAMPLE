"""
Customer Search Service - Trigram, Vector, and Hybrid search (PostgreSQL)
"""
from typing import List, Dict, Any
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.embeddings import generate_embedding
from shared.hybrid_rank import reciprocal_rank_fusion, SearchResult
from shared.database.postgresql import get_pooled_connection


class CustomerSearchService:
    """Search service for customers using PostgreSQL with trigram and vector search."""
    
    def __init__(self):
        pass
    
    def _get_connection(self):
        """Get a pooled database connection."""
        return get_pooled_connection()
    
    def _row_to_dict(self, row, columns) -> Dict[str, Any]:
        """Convert row to dictionary."""
        result = {}
        for i, col in enumerate(columns):
            value = row[i]
            if hasattr(value, 'isoformat'):
                value = value.isoformat()
            elif hasattr(value, 'hex'):  # UUID
                value = str(value)
            result[col] = value
        return result
    
    def trigram_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search customers using trigram similarity (pg_trgm).
        Searches on first_name, last_name, and email.
        Uses explicit text casts to avoid type-mismatch errors.
        """
        search_query = """
            SELECT customer_id, first_name, last_name, email, phone, city, country,
                   GREATEST(
                       similarity(first_name::text, %s::text),
                       similarity(last_name::text, %s::text),
                       similarity((first_name || ' ' || last_name)::text, %s::text),
                       similarity(email::text, %s::text)
                   ) AS similarity_score
            FROM customers
            WHERE first_name::text %% %s::text
               OR last_name::text %% %s::text
               OR (first_name || ' ' || last_name)::text %% %s::text
               OR email::text %% %s::text
            ORDER BY similarity_score DESC
            LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Ensure pg_trgm is enabled
                    try:
                        cursor.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm";')
                        conn.commit()
                    except Exception:
                        conn.rollback()
                    
                    # Set similarity threshold
                    cursor.execute("SET pg_trgm.similarity_threshold = 0.1")
                    
                    cursor.execute(search_query, (
                        query, query, query, query,
                        query, query, query, query,
                        limit
                    ))
                    columns = [desc[0] for desc in cursor.description]
                    results = []
                    for row in cursor.fetchall():
                        data = self._row_to_dict(row, columns)
                        data['search_score'] = float(data.pop('similarity_score', 0))
                        data['search_type'] = 'trigram'
                        results.append(data)
                    return results
        except Exception as e:
            print(f"Error in trigram search: {e}")
            return []
    
    def vector_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search customers using vector similarity (pgvector).
        Uses cosine distance on name embeddings.
        PostgreSQL stores 3072-dim vectors (azure_ai extension default for text-embedding-3-large).
        """
        # Generate query embedding with 3072 dimensions to match DB column
        query_embedding = generate_embedding(query, dimensions=3072)
        
        if not query_embedding:
            print("Could not generate embedding, falling back to trigram search")
            return self.trigram_search(query, limit)
        
        # Vector search using pgvector
        search_query = """
            SELECT customer_id, first_name, last_name, email, phone, city, country,
                   1 - (name_embedding <=> %s::vector) AS similarity_score
            FROM customers
            WHERE name_embedding IS NOT NULL
            ORDER BY name_embedding <=> %s::vector
            LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    embedding_str = str(query_embedding)
                    cursor.execute(search_query, (embedding_str, embedding_str, limit))
                    columns = [desc[0] for desc in cursor.description]
                    results = []
                    for row in cursor.fetchall():
                        data = self._row_to_dict(row, columns)
                        data['search_score'] = float(data.pop('similarity_score', 0))
                        data['search_type'] = 'vector'
                        results.append(data)
                    return results
        except Exception as e:
            print(f"Vector search failed: {e}. Falling back to trigram search.")
            return self.trigram_search(query, limit)
    
    def hybrid_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Hybrid search combining trigram and vector search using RRF.
        """
        # Get results from both methods
        trigram_results = self.trigram_search(query, limit=limit * 2)
        vector_results = self.vector_search(query, limit=limit * 2)
        
        # Convert to SearchResult objects
        trigram_sr = [
            SearchResult(
                id=r['customer_id'], 
                data=r, 
                score=r.get('search_score', 0), 
                source='trigram'
            )
            for r in trigram_results
        ]
        vector_sr = [
            SearchResult(
                id=r['customer_id'], 
                data=r, 
                score=r.get('search_score', 0), 
                source='vector'
            )
            for r in vector_results
        ]
        
        # Apply RRF
        combined = reciprocal_rank_fusion(trigram_sr, vector_sr)
        
        # Convert back to dict format
        results = []
        for sr in combined[:limit]:
            data = sr.data.copy()
            data['search_score'] = sr.score
            data['search_type'] = 'hybrid'
            results.append(data)
        
        return results
