"""
Search Service - Keyword, Vector, and Hybrid search for products (Azure SQL)
Using mssql-python driver with SQL authentication
"""
from mssql_python import connect
import json
from typing import List, Dict, Any, Optional
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import azure_sql_config, openai_config
from shared.embeddings import generate_embedding
from shared.hybrid_rank import reciprocal_rank_fusion, SearchResult


class ProductSearchService:
    """Search service for products using Azure SQL with mssql-python."""
    
    def __init__(self):
        self.config = azure_sql_config
    
    def _get_connection(self):
        """Get database connection using mssql-python with SQL authentication."""
        return self.config.get_connection()
    
    def _row_to_dict(self, row, columns) -> Dict[str, Any]:
        """Convert row to dictionary."""
        result = {}
        for i, col in enumerate(columns):
            if col != 'description_embedding':  # Don't include embedding in results
                result[col] = row[i]
        return result
    
    def keyword_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Keyword search using LIKE and CONTAINS (full-text if available).
        Falls back to LIKE if full-text is not configured.
        """
        # Simple LIKE-based search (works without full-text index)
        search_query = """
            SELECT TOP (?) 
                sku, name, description, price, currency, tags, stock, category,
                (CASE 
                    WHEN name LIKE ? THEN 3
                    WHEN description LIKE ? THEN 2
                    WHEN tags LIKE ? THEN 1
                    ELSE 0
                END) AS relevance_score
            FROM products
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY relevance_score DESC, name
        """
        
        pattern = f'%{query}%'
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(search_query, (limit, pattern, pattern, pattern, pattern, pattern, pattern))
                columns = [col[0] for col in cursor.description]
                results = []
                for row in cursor.fetchall():
                    data = self._row_to_dict(row, columns)
                    data['search_score'] = row[-1]  # relevance_score
                    data['search_type'] = 'keyword'
                    results.append(data)
                return results
        except Exception as e:
            print(f"Error in keyword search: {e}")
            return []
    
    def vector_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Vector similarity search using Azure SQL VECTOR_DISTANCE.
        Requires embeddings to be stored and vector index created.
        """
        # Generate query embedding
        query_embedding = generate_embedding(query)
        
        if not query_embedding:
            print("Could not generate embedding, falling back to keyword search")
            return self.keyword_search(query, limit)
        
        embedding_json = json.dumps(query_embedding)
        
        # Vector search using VECTOR_DISTANCE
        # Note: Azure SQL max 1998 dimensions, using 1536 for compatibility
        search_query = """
            SELECT TOP (?)
                sku, name, description, price, currency, tags, stock, category,
                VECTOR_DISTANCE('cosine', description_embedding, CAST(? AS VECTOR(1536))) AS distance
            FROM products
            WHERE description_embedding IS NOT NULL
            ORDER BY distance ASC
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(search_query, (limit, embedding_json))
                columns = [col[0] for col in cursor.description]
                results = []
                for row in cursor.fetchall():
                    data = self._row_to_dict(row, columns)
                    # Convert distance to similarity (1 - distance for cosine)
                    data['search_score'] = 1 - row[-1] if row[-1] else 0
                    data['search_type'] = 'vector'
                    results.append(data)
                return results
        except Exception as e:
            print(f"Vector search failed: {e}. Falling back to keyword search.")
            return self.keyword_search(query, limit)
    
    def hybrid_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Hybrid search combining keyword and vector search using RRF.
        """
        # Get results from both methods
        keyword_results = self.keyword_search(query, limit=limit * 2)
        vector_results = self.vector_search(query, limit=limit * 2)
        
        # Convert to SearchResult objects
        keyword_sr = [
            SearchResult(id=r['sku'], data=r, score=r.get('search_score', 0), source='keyword')
            for r in keyword_results
        ]
        vector_sr = [
            SearchResult(id=r['sku'], data=r, score=r.get('search_score', 0), source='vector')
            for r in vector_results
        ]
        
        # Apply RRF
        combined = reciprocal_rank_fusion(keyword_sr, vector_sr)
        
        # Convert back to dict format
        results = []
        for sr in combined[:limit]:
            data = sr.data.copy()
            data['search_score'] = sr.score
            data['search_type'] = 'hybrid'
            results.append(data)
        
        return results
    
    def find_similar_products(self, description: str, limit: int = 5, exclude_sku: str = None) -> List[Dict[str, Any]]:
        """Find products similar to a given description."""
        results = self.vector_search(description, limit=limit + 1)
        
        # Exclude the source product
        if exclude_sku:
            results = [r for r in results if r.get('sku') != exclude_sku]
        
        return results[:limit]
