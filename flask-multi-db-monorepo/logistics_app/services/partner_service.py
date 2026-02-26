"""
Partner Service - Database operations for delivery partners (MongoDB vCore)
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


class PartnerService:
    """Service for partner CRUD operations using MongoDB vCore."""
    
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
        """Convert MongoDB document to dictionary with string _id."""
        if doc is None:
            return None
        
        result = dict(doc)
        if '_id' in result:
            result['_id'] = str(result['_id'])
        if 'created_at' in result and isinstance(result['created_at'], datetime):
            result['created_at'] = result['created_at'].isoformat()
        if 'updated_at' in result and isinstance(result['updated_at'], datetime):
            result['updated_at'] = result['updated_at'].isoformat()
        return result
    
    def get_all_partners(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get all partners."""
        db = self._get_db()
        
        query = {}
        if active_only:
            query['active'] = True
        
        try:
            cursor = db.partners.find(query).sort('name', 1)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error fetching partners: {e}")
            return []
    
    def count_partners(self) -> int:
        """Count total partners."""
        try:
            db = self._get_db()
            return db.partners.count_documents({})
        except Exception as e:
            print(f"Error counting partners: {e}")
            return 0
    
    def get_partner_by_id(self, partner_id: str) -> Optional[Dict[str, Any]]:
        """Get partner by ID."""
        db = self._get_db()
        
        try:
            # Try as ObjectId first, then as partner_id field
            doc = db.partners.find_one({'_id': ObjectId(partner_id)})
            if not doc:
                doc = db.partners.find_one({'partner_id': partner_id})
            return self._doc_to_dict(doc)
        except Exception as e:
            # If ObjectId conversion fails, try partner_id field
            try:
                doc = db.partners.find_one({'partner_id': partner_id})
                return self._doc_to_dict(doc)
            except Exception as e2:
                print(f"Error fetching partner: {e2}")
                return None
    
    def create_partner(self, data: Dict[str, Any]) -> str:
        """Create a new partner."""
        db = self._get_db()
        
        partner_id = str(uuid.uuid4())[:8].upper()
        
        doc = {
            'partner_id': partner_id,
            'name': data['name'],
            'contact_email': data['contact_email'],
            'contact_phone': data.get('contact_phone', ''),
            'service_areas': data.get('service_areas', []),
            'vehicle_types': data.get('vehicle_types', []),
            'active': data.get('active', True),
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        try:
            result = db.partners.insert_one(doc)
            return partner_id
        except Exception as e:
            print(f"Error creating partner: {e}")
            raise
    
    def update_partner(self, partner_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing partner."""
        db = self._get_db()
        
        update_doc = {
            '$set': {
                'name': data['name'],
                'contact_email': data['contact_email'],
                'contact_phone': data.get('contact_phone', ''),
                'service_areas': data.get('service_areas', []),
                'vehicle_types': data.get('vehicle_types', []),
                'active': data.get('active', True),
                'updated_at': datetime.utcnow()
            }
        }
        
        try:
            result = db.partners.update_one(
                {'partner_id': partner_id},
                update_doc
            )
            return result.modified_count > 0
        except Exception as e:
            print(f"Error updating partner: {e}")
            raise
    
    def delete_partner(self, partner_id: str) -> bool:
        """Delete a partner."""
        db = self._get_db()
        
        try:
            result = db.partners.delete_one({'partner_id': partner_id})
            return result.deleted_count > 0
        except Exception as e:
            print(f"Error deleting partner: {e}")
            raise

    def search_partners(self, query: str) -> List[Dict[str, Any]]:
        """Search partners by name, email, phone, service areas, or vehicle types."""
        db = self._get_db()

        regex = {'$regex': query, '$options': 'i'}
        try:
            cursor = db.partners.find({
                '$or': [
                    {'name': regex},
                    {'contact_email': regex},
                    {'contact_phone': regex},
                    {'service_areas': regex},
                    {'vehicle_types': regex},
                    {'partner_id': regex},
                ]
            }).sort('name', 1)
            return [self._doc_to_dict(doc) for doc in cursor]
        except Exception as e:
            print(f"Error searching partners: {e}")
            return []
