"""
Delivery Service - Database operations for deliveries (MongoDB vCore)
"""
from pymongo import MongoClient
from typing import List, Dict, Any, Optional
from datetime import datetime
from bson import ObjectId
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import mongodb_config
from shared.embeddings import generate_embedding


class DeliveryService:
    """Service for delivery CRUD operations using MongoDB vCore."""
    
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
        
        # Convert datetime fields
        for field in ['created_at', 'updated_at', 'eta', 'last_update']:
            if field in result and isinstance(result[field], datetime):
                result[field] = result[field].isoformat()
        
        # Convert events timestamps
        if 'events' in result:
            for event in result['events']:
                if 'timestamp' in event and isinstance(event['timestamp'], datetime):
                    event['timestamp'] = event['timestamp'].isoformat()
        
        # Remove embedding from response
        result.pop('content_embedding', None)
        
        return result
    
    def get_all_deliveries(self, status: str = '', limit: int = 100) -> List[Dict[str, Any]]:
        """Get all deliveries, optionally filtered by status."""
        db = self._get_db()
        
        query = {}
        if status:
            query['status'] = status
        
        try:
            cursor = db.deliveries.find(query).sort('created_at', -1).limit(limit)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching deliveries: {e}")
            return []
    
    def get_unassigned_deliveries(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get deliveries with no partner assigned."""
        db = self._get_db()
        
        # Find deliveries where partner_id is null, empty, or doesn't exist
        query = {
            '$or': [
                {'partner_id': None},
                {'partner_id': ''},
                {'partner_id': {'$exists': False}}
            ]
        }
        
        try:
            cursor = db.deliveries.find(query).sort('created_at', -1).limit(limit)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching unassigned deliveries: {e}")
            return []
    
    def get_assigned_deliveries(self, status: str = '', limit: int = 100) -> List[Dict[str, Any]]:
        """Get deliveries with a partner assigned."""
        db = self._get_db()
        
        # Find deliveries where partner_id exists and is not null/empty
        query = {
            'partner_id': {'$exists': True, '$ne': None, '$ne': ''}
        }
        
        if status:
            query['status'] = status
        
        try:
            cursor = db.deliveries.find(query).sort('created_at', -1).limit(limit)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching assigned deliveries: {e}")
            return []
    
    def count_deliveries(self) -> int:
        """Count total deliveries."""
        try:
            db = self._get_db()
            return db.deliveries.count_documents({})
        except Exception as e:
            print(f"Error counting deliveries: {e}")
            return 0
    
    def count_by_status(self, status: str) -> int:
        """Count deliveries by status."""
        try:
            db = self._get_db()
            return db.deliveries.count_documents({'status': status})
        except Exception as e:
            print(f"Error counting deliveries by status: {e}")
            return 0
    
    def get_delivery_by_id(self, delivery_id: str) -> Optional[Dict[str, Any]]:
        """Get delivery by ID."""
        db = self._get_db()
        
        try:
            doc = db.deliveries.find_one({'delivery_id': delivery_id})
            if not doc:
                try:
                    doc = db.deliveries.find_one({'_id': ObjectId(delivery_id)})
                except:
                    pass
            return self._doc_to_dict(doc)
        except Exception as e:
            print(f"Error fetching delivery: {e}")
            return None
    
    def get_by_tracking_number(self, tracking_number: str) -> Optional[Dict[str, Any]]:
        """Get delivery by tracking number."""
        db = self._get_db()
        
        try:
            doc = db.deliveries.find_one({'tracking_number': tracking_number.upper()})
            return self._doc_to_dict(doc)
        except Exception as e:
            print(f"Error fetching delivery by tracking: {e}")
            return None
    
    def get_by_order_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get delivery by order ID."""
        db = self._get_db()
        
        try:
            doc = db.deliveries.find_one({'order_id': order_id})
            return self._doc_to_dict(doc)
        except Exception as e:
            print(f"Error fetching delivery by order: {e}")
            return None
    
    def get_deliveries_by_partner(self, partner_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get deliveries assigned to a partner."""
        db = self._get_db()
        
        try:
            cursor = db.deliveries.find({'partner_id': partner_id}).sort('created_at', -1).limit(limit)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching partner deliveries: {e}")
            return []
    
    def get_recent_deliveries(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most recent deliveries."""
        db = self._get_db()
        
        try:
            cursor = db.deliveries.find().sort('created_at', -1).limit(limit)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching recent deliveries: {e}")
            return []
    
    def create_delivery(self, data: Dict[str, Any]) -> str:
        """Create a new delivery."""
        db = self._get_db()
        
        delivery_id = str(uuid.uuid4())[:8].upper()
        tracking_number = f"TRK{uuid.uuid4().hex[:10].upper()}"
        
        # Create searchable content for embedding
        searchable_content = f"{data['customer_name']} {data['address']} {data['city']} {data.get('notes', '')}"
        embedding = generate_embedding(searchable_content)
        
        now = datetime.utcnow()
        
        doc = {
            'delivery_id': delivery_id,
            'tracking_number': tracking_number,
            'order_id': data['order_id'],
            'customer_name': data['customer_name'],
            'partner_id': data.get('partner_id'),
            'status': 'pending',
            'status_text': 'Delivery created, awaiting pickup',
            'address': {
                'street': data['address'],
                'city': data['city'],
                'postal_code': data.get('postal_code', ''),
                'country': data.get('country', 'France')
            },
            'notes': data.get('notes', ''),
            'eta': None,
            'events': [
                {
                    'timestamp': now,
                    'status': 'pending',
                    'description': 'Delivery created',
                    'location': ''
                }
            ],
            'content_embedding': embedding,
            'created_at': now,
            'updated_at': now,
            'last_update': now
        }
        
        try:
            result = db.deliveries.insert_one(doc)
            return delivery_id
        except Exception as e:
            print(f"Error creating delivery: {e}")
            raise
    
    def update_status(self, delivery_id: str, status: str, status_text: str = '', location: str = '') -> bool:
        """Update delivery status and add event."""
        db = self._get_db()
        
        valid_statuses = ['pending', 'picked_up', 'in_transit', 'out_for_delivery', 'delivered', 'failed', 'returned']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        now = datetime.utcnow()
        
        # Default status texts
        default_texts = {
            'pending': 'Awaiting pickup',
            'picked_up': 'Package picked up from sender',
            'in_transit': 'Package in transit',
            'out_for_delivery': 'Out for delivery',
            'delivered': 'Package delivered successfully',
            'failed': 'Delivery attempt failed',
            'returned': 'Package returned to sender'
        }
        
        if not status_text:
            status_text = default_texts.get(status, status)
        
        event = {
            'timestamp': now,
            'status': status,
            'description': status_text,
            'location': location
        }
        
        try:
            result = db.deliveries.update_one(
                {'delivery_id': delivery_id},
                {
                    '$set': {
                        'status': status,
                        'status_text': status_text,
                        'last_update': now,
                        'updated_at': now
                    },
                    '$push': {
                        'events': event
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating delivery status: {e}")
            raise
    
    def assign_partner(self, delivery_id: str, partner_id: str) -> bool:
        """Assign a partner to a delivery."""
        db = self._get_db()
        
        now = datetime.utcnow()
        
        try:
            result = db.deliveries.update_one(
                {'delivery_id': delivery_id},
                {
                    '$set': {
                        'partner_id': partner_id,
                        'updated_at': now
                    },
                    '$push': {
                        'events': {
                            'timestamp': now,
                            'status': 'assigned',
                            'description': f'Assigned to partner {partner_id}',
                            'location': ''
                        }
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error assigning partner: {e}")
            raise
