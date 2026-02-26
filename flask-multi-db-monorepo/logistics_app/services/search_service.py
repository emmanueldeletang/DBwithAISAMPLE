"""
Search Service - Keyword, Vector, and Hybrid search for deliveries (MongoDB vCore)
"""
from pymongo import MongoClient
from typing import List, Dict, Any
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import mongodb_config
from shared.embeddings import generate_embedding
from shared.hybrid_rank import reciprocal_rank_fusion, SearchResult


class LogisticsSearchService:
    """Search service for logistics using MongoDB vCore with vector search."""
    
    def __init__(self):
        self.config = mongodb_config
        self._client = None
        self._db = None
    
    def _get_db(self):
        """Get database connection."""
        if self._client is None:
            self._client = MongoClient(self.config.connection_string)
            self._db = self._client[self.config.database]
        return self._db
    
    def _doc_to_dict(self, doc: dict) -> Dict[str, Any]:
        """Convert MongoDB document to dictionary."""
        if doc is None:
            return None
        
        result = dict(doc)
        if '_id' in result:
            result['_id'] = str(result['_id'])
        
        for field in ['created_at', 'updated_at', 'eta', 'last_update']:
            if field in result and isinstance(result[field], datetime):
                result[field] = result[field].isoformat()
        
        result.pop('content_embedding', None)
        return result
    
    def keyword_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Keyword search using MongoDB text search.
        Searches on customer_name, status_text, notes, and address fields.
        """
        db = self._get_db()
        
        try:
            # Use $text search if text index exists
            cursor = db.deliveries.find(
                {'$text': {'$search': query}},
                {'score': {'$meta': 'textScore'}}
            ).sort([('score', {'$meta': 'textScore'})]).limit(limit)
            
            results = []
            for doc in cursor:
                data = self._doc_to_dict(doc)
                data['search_score'] = doc.get('score', 0)
                data['search_type'] = 'keyword'
                results.append(data)
            
            return results
        
        except Exception as e:
            print(f"Text search failed: {e}. Falling back to regex search.")
            
            # Fallback to regex search
            regex_pattern = {'$regex': query, '$options': 'i'}
            cursor = db.deliveries.find({
                '$or': [
                    {'customer_name': regex_pattern},
                    {'status_text': regex_pattern},
                    {'notes': regex_pattern},
                    {'address.street': regex_pattern},
                    {'address.city': regex_pattern},
                    {'tracking_number': regex_pattern}
                ]
            }).limit(limit)
            
            results = []
            for doc in cursor:
                data = self._doc_to_dict(doc)
                data['search_score'] = 1.0
                data['search_type'] = 'keyword'
                results.append(data)
            
            return results
    
    def vector_search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Vector similarity search using Cosmos DB for MongoDB vCore cosmosSearch.
        """
        db = self._get_db()
        
        # Generate query embedding
        query_embedding = generate_embedding(query)
        
        if not query_embedding:
            print("Could not generate embedding, falling back to keyword search")
            return self.keyword_search(query, limit)
        
        try:
            # Vector search using cosmosSearch aggregation
            pipeline = [
                {
                    '$search': {
                        'cosmosSearch': {
                            'vector': query_embedding,
                            'path': 'content_embedding',
                            'k': limit
                        },
                        'returnStoredSource': True
                    }
                },
                {
                    '$project': {
                        'delivery_id': 1,
                        'tracking_number': 1,
                        'order_id': 1,
                        'customer_name': 1,
                        'partner_id': 1,
                        'status': 1,
                        'status_text': 1,
                        'address': 1,
                        'notes': 1,
                        'events': 1,
                        'created_at': 1,
                        'last_update': 1,
                        'search_score': {'$meta': 'searchScore'}
                    }
                }
            ]
            
            cursor = db.deliveries.aggregate(pipeline)
            
            results = []
            for doc in cursor:
                data = self._doc_to_dict(doc)
                data['search_score'] = doc.get('search_score', 0)
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
            SearchResult(
                id=r.get('delivery_id') or r.get('_id'),
                data=r,
                score=r.get('search_score', 0),
                source='keyword'
            )
            for r in keyword_results
        ]
        vector_sr = [
            SearchResult(
                id=r.get('delivery_id') or r.get('_id'),
                data=r,
                score=r.get('search_score', 0),
                source='vector'
            )
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
