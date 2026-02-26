"""
Search service for Azure SQL using mssql-python driver with vector search support
Uses Azure SQL VECTOR type and VECTOR_DISTANCE function for similarity search
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from shared.database.azure_sql import get_db
from shared.embeddings import generate_embedding


class AzureSQLSearch:
    """Search service using mssql-python driver with vector search."""
    
    def keyword_search(self, query: str, limit: int = 20):
        """Keyword search using LIKE."""
        pattern = f'%{query}%'
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT TOP (?) sku, name, description, price, currency, tags, stock, category
            FROM products
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY name
        """, (limit, pattern, pattern, pattern))
        
        columns = [col[0] for col in cursor.description]
        results = []
        for row in cursor.fetchall():
            data = dict(zip(columns, row))
            data['search_type'] = 'keyword'
            data['search_score'] = 1.0  # Keyword matches get base score
            results.append(data)
        conn.close()
        return results
    
    def vector_search(self, query: str, limit: int = 20):
        """
        Vector similarity search using Azure SQL VECTOR_DISTANCE function.
        Generates embedding for query and finds similar products.
        """
        # Generate embedding for the search query
        query_embedding = generate_embedding(query)
        
        if not query_embedding:
            print("Could not generate embedding, falling back to keyword search")
            return self.keyword_search(query, limit)
        
        # Convert embedding to JSON format for VECTOR type
        embedding_json = json.dumps(query_embedding)
        
        conn = get_db()
        cursor = conn.cursor()
        
        try:
            # Use VECTOR_DISTANCE with cosine similarity
            # Lower distance = more similar, so we order ASC
            cursor.execute("""
                SELECT TOP (?)
                    sku, name, description, price, currency, tags, stock, category,
                    VECTOR_DISTANCE('cosine', description_embedding, CAST(? AS VECTOR(1536))) AS distance
                FROM products
                WHERE description_embedding IS NOT NULL
                ORDER BY distance ASC
            """, (limit, embedding_json))
            
            columns = [col[0] for col in cursor.description]
            results = []
            for row in cursor.fetchall():
                data = dict(zip(columns[:-1], row[:-1]))  # Exclude distance from dict
                distance = row[-1]
                # Convert distance to similarity score (1 - distance for cosine)
                data['search_score'] = 1.0 - float(distance) if distance is not None else 0
                data['search_type'] = 'vector'
                results.append(data)
            
            conn.close()
            return results
            
        except Exception as e:
            print(f"Vector search failed: {e}")
            conn.close()
            return self.keyword_search(query, limit)
    
    def hybrid_search(self, query: str, limit: int = 20):
        """
        Hybrid search combining keyword and vector search using Reciprocal Rank Fusion (RRF).
        """
        # Get results from both search methods
        keyword_results = self.keyword_search(query, limit * 2)
        vector_results = self.vector_search(query, limit * 2)
        
        # RRF constants
        k = 60  # Standard RRF constant
        
        # Calculate RRF scores
        rrf_scores = {}
        
        # Add keyword results with rank-based scoring
        for rank, result in enumerate(keyword_results):
            sku = result['sku']
            rrf_scores[sku] = {
                'data': result,
                'score': 1.0 / (k + rank + 1)
            }
        
        # Add vector results with rank-based scoring
        for rank, result in enumerate(vector_results):
            sku = result['sku']
            vector_rrf = 1.0 / (k + rank + 1)
            
            if sku in rrf_scores:
                # Combine scores for items in both result sets
                rrf_scores[sku]['score'] += vector_rrf
                rrf_scores[sku]['data']['search_type'] = 'hybrid'
            else:
                rrf_scores[sku] = {
                    'data': result,
                    'score': vector_rrf
                }
        
        # Sort by combined RRF score and take top results
        sorted_results = sorted(rrf_scores.values(), key=lambda x: x['score'], reverse=True)
        
        results = []
        for item in sorted_results[:limit]:
            data = item['data'].copy()
            data['search_score'] = item['score']
            data['search_type'] = 'hybrid'
            results.append(data)
        
        return results


def search_products(query: str, limit: int = 20, search_type: str = 'hybrid'):
    """
    Convenience function for product search.
    
    Args:
        query: Search query string
        limit: Maximum number of results
        search_type: 'keyword', 'vector', or 'hybrid'
    """
    search = AzureSQLSearch()
    
    if search_type == 'keyword':
        return search.keyword_search(query, limit)
    elif search_type == 'vector':
        return search.vector_search(query, limit)
    else:
        return search.hybrid_search(query, limit)