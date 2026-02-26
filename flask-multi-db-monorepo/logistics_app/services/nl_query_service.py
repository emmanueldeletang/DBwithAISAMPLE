"""
Natural Language Query Service for MongoDB
Uses Azure OpenAI to convert natural language questions to MongoDB queries.
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from openai import AzureOpenAI
from pymongo import MongoClient
from bson import json_util
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import mongodb_config


class NLQueryService:
    """Service for natural language queries against MongoDB."""
    
    def __init__(self):
        self.config = mongodb_config
        self._client = None
        self._db = None
        
        # Azure OpenAI client
        self.openai_client = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2024-02-15-preview'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
        )
        self.chat_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o')
    
    def _get_db(self):
        """Get database connection."""
        if self._client is None:
            self._client = MongoClient(self.config.connection_string)
            self._db = self._client[self.config.database]
        return self._db
    
    def _serialize_doc(self, doc: dict) -> dict:
        """Serialize MongoDB document for JSON output."""
        return json.loads(json_util.dumps(doc))
    
    def get_schema_context(self) -> str:
        """Get database schema for the AI context."""
        return """
## MongoDB Database: logisticsdb

### Collection: deliveries
Fields:
- delivery_id (string): Unique identifier like "DEL001"
- tracking_number (string): Tracking number like "TRK1A2B3C4D5E"
- order_id (string): Reference to order (UUID)
- customer_name (string): Full name like "Jean Dupont"
- partner_id (string): Partner ID like "PART001" or null if not assigned
- status (string): One of: "pending", "picked_up", "in_transit", "out_for_delivery", "delivered", "failed"
- status_text (string): Human-readable status
- address (object): { street, city, postal_code, country }
- notes (string): Delivery instructions
- eta (datetime): Estimated arrival
- events (array): Tracking history with timestamp, status, description, location
- created_at, updated_at (datetime)

### Collection: partners
Fields:
- partner_id (string): Unique identifier like "PART001"
- name (string): Company name like "SpeedyExpress"
- contact_email (string)
- contact_phone (string)
- service_areas (array of strings): Cities served like ["Paris", "Lyon"]
- vehicle_types (array of strings): Fleet types like ["Van", "Truck"]
- active (boolean)
- created_at, updated_at (datetime)

### Common Status Values:
- pending: Awaiting dispatch
- picked_up: Picked up by partner
- in_transit: On the way
- out_for_delivery: Last mile
- delivered: Successfully delivered
- failed: Delivery failed
"""
    
    def generate_query(self, question: str) -> Dict[str, Any]:
        """
        Use Azure OpenAI to convert natural language to MongoDB query.
        Returns either a find query or an aggregation pipeline.
        """
        system_prompt = f"""You are a MongoDB query generator. Convert natural language questions about a logistics/delivery database into MongoDB queries.

{self.get_schema_context()}

IMPORTANT RULES:
1. Return ONLY valid JSON, no markdown, no explanation
2. Use the exact field names from the schema
3. For counts/statistics, use aggregation pipelines
4. For listing/searching, use find queries
5. Always limit results to 50 unless specifically asked for more
6. Use case-insensitive regex for text searches
7. For date queries, use proper MongoDB date operators

Return JSON in this format:
{{
  "query_type": "find" or "aggregation",
  "collection": "deliveries" or "partners",
  "description": "Brief description of what the query does",
  "query": {{ ... }} // For find: the filter object
  "projection": {{ ... }} // Optional: fields to include/exclude
  "sort": {{ ... }} // Optional: sort order
  "limit": number // Optional: max results
  "pipeline": [ ... ] // For aggregation: array of pipeline stages
}}
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ],
                temperature=0,
                max_tokens=1000
            )
            
            result_text = response.choices[0].message.content.strip()
            
            # Clean up response - remove markdown if present
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1])
            
            return json.loads(result_text)
            
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse AI response: {str(e)}", "raw": result_text}
        except Exception as e:
            return {"error": f"Failed to generate query: {str(e)}"}
    
    def execute_query(self, query_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a MongoDB query specification."""
        if "error" in query_spec:
            return query_spec
        
        db = self._get_db()
        query_type = query_spec.get("query_type", "find")
        collection_name = query_spec.get("collection", "deliveries")
        
        try:
            collection = db[collection_name]
            
            if query_type == "aggregation":
                pipeline = query_spec.get("pipeline", [])
                results = list(collection.aggregate(pipeline))
                
                return {
                    "success": True,
                    "query_type": "aggregation",
                    "collection": collection_name,
                    "description": query_spec.get("description", ""),
                    "count": len(results),
                    "results": [self._serialize_doc(doc) for doc in results]
                }
            
            else:  # find query
                query = query_spec.get("query", {})
                projection = query_spec.get("projection")
                sort = query_spec.get("sort")
                limit = query_spec.get("limit", 50)
                
                cursor = collection.find(query, projection)
                
                if sort:
                    cursor = cursor.sort(list(sort.items()))
                
                cursor = cursor.limit(limit)
                results = list(cursor)
                
                return {
                    "success": True,
                    "query_type": "find",
                    "collection": collection_name,
                    "description": query_spec.get("description", ""),
                    "count": len(results),
                    "results": [self._serialize_doc(doc) for doc in results]
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Query execution failed: {str(e)}",
                "query_spec": query_spec
            }
    
    def ask(self, question: str) -> Dict[str, Any]:
        """
        Main method: Ask a natural language question and get results.
        """
        # Generate the query
        query_spec = self.generate_query(question)
        
        if "error" in query_spec:
            return {
                "success": False,
                "question": question,
                "error": query_spec["error"]
            }
        
        # Execute the query
        result = self.execute_query(query_spec)
        result["question"] = question
        result["generated_query"] = query_spec
        
        return result
    
    def get_suggested_questions(self) -> List[str]:
        """Get a list of suggested questions for the UI."""
        return [
            "How many deliveries are pending?",
            "Show me all deliveries in Paris",
            "Which partner has the most deliveries?",
            "List all failed deliveries",
            "What are the deliveries by status?",
            "Show pending deliveries that need to be dispatched",
            "How many deliveries per city?",
            "List all active partners",
            "Which cities have the most pending deliveries?",
            "Show deliveries for customer Jean Dupont",
            "What's the delivery breakdown by partner?",
            "List deliveries created in the last 7 days",
        ]
