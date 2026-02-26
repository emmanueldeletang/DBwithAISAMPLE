"""
Customer Service - Database operations for customers (PostgreSQL)
"""
import psycopg2.extras
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.embeddings import generate_embedding
from shared.database.postgresql import get_pooled_connection


class CustomerService:
    """Service for customer CRUD operations using PostgreSQL."""
    
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
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[col] = value
        return result
    
    def get_all_customers(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        """Get paginated list of customers."""
        offset = (page - 1) * per_page
        
        query = """
            SELECT customer_id, first_name, last_name, email, phone, 
                   address, city, country, created_at
            FROM customers
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (per_page, offset))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching customers: {e}")
            return []
    
    def count_customers(self) -> int:
        """Count total customers."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) FROM customers")
                    return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error counting customers: {e}")
            return 0
    
    def get_customer_by_id(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by ID."""
        query = """
            SELECT customer_id, first_name, last_name, email, phone,
                   address, city, country, created_at
            FROM customers
            WHERE customer_id = %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (customer_id,))
                    columns = [desc[0] for desc in cursor.description]
                    row = cursor.fetchone()
                    if row:
                        return self._row_to_dict(row, columns)
                    return None
        except Exception as e:
            print(f"Error fetching customer: {e}")
            return None
    
    def create_customer(self, data: Dict[str, Any]) -> str:
        """Create a new customer."""
        customer_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO customers (customer_id, first_name, last_name, email, phone, 
                                  address, city, country)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (
                        customer_id,
                        data['first_name'],
                        data['last_name'],
                        data['email'],
                        data.get('phone', ''),
                        data.get('address', ''),
                        data.get('city', ''),
                        data.get('country', '')
                    ))
                conn.commit()
                return customer_id
        except Exception as e:
            print(f"Error creating customer: {e}")
            raise
    
    def update_customer(self, customer_id: str, data: Dict[str, Any]) -> bool:
        """Update an existing customer."""
        query = """
            UPDATE customers
            SET first_name = %s, last_name = %s, email = %s, phone = %s,
                address = %s, city = %s, country = %s
            WHERE customer_id = %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (
                        data['first_name'],
                        data['last_name'],
                        data['email'],
                        data.get('phone', ''),
                        data.get('address', ''),
                        data.get('city', ''),
                        data.get('country', ''),
                        customer_id
                    ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating customer: {e}")
            raise
    
    def delete_customer(self, customer_id: str) -> bool:
        """Delete a customer."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM customers WHERE customer_id = %s", (customer_id,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error deleting customer: {e}")
            raise
