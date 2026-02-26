"""
Order Service - Database operations for orders (PostgreSQL)
"""
import psycopg2.extras
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.database.postgresql import get_pooled_connection


class OrderService:
    """Service for order CRUD operations using PostgreSQL."""
    
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
    
    def get_all_orders(self, page: int = 1, per_page: int = 20, status: str = '') -> List[Dict[str, Any]]:
        """Get paginated list of orders."""
        offset = (page - 1) * per_page
        
        query = """
            SELECT o.order_id, o.customer_id, o.order_date, o.status, 
                   o.total_amount, o.currency,
                   c.first_name, c.last_name, c.email
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
        """
        params = []
        
        if status:
            query += " WHERE o.status = %s"
            params.append(status)
        
        query += " ORDER BY o.order_date DESC LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    columns = [desc[0] for desc in cursor.description]
                    return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching orders: {e}")
            return []
    
    def count_orders(self, status: str = '') -> int:
        """Count total orders."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    if status:
                        cursor.execute("SELECT COUNT(*) FROM orders WHERE status = %s", (status,))
                    else:
                        cursor.execute("SELECT COUNT(*) FROM orders")
                    return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error counting orders: {e}")
            return 0
    
    def get_order_by_id(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get order by ID."""
        query = """
            SELECT order_id, customer_id, order_date, status, total_amount, currency
            FROM orders
            WHERE order_id = %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (order_id,))
                    columns = [desc[0] for desc in cursor.description]
                    row = cursor.fetchone()
                    if row:
                        return self._row_to_dict(row, columns)
                    return None
        except Exception as e:
            print(f"Error fetching order: {e}")
            return None
    
    def get_order_items(self, order_id: str) -> List[Dict[str, Any]]:
        """Get items for an order."""
        query = """
            SELECT order_item_id, order_id, product_sku, product_name, 
                   category, quantity, unit_price
            FROM order_items
            WHERE order_id = %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (order_id,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching order items: {e}")
            return []
    
    def get_orders_by_customer(self, customer_id: str) -> List[Dict[str, Any]]:
        """Get all orders for a customer."""
        query = """
            SELECT order_id, customer_id, order_date, status, total_amount, currency
            FROM orders
            WHERE customer_id = %s
            ORDER BY order_date DESC
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (customer_id,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching customer orders: {e}")
            return []
    
    def get_recent_orders(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Get most recent orders."""
        query = """
            SELECT o.order_id, o.customer_id, o.order_date, o.status, 
                   o.total_amount, o.currency,
                   c.first_name, c.last_name
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            ORDER BY o.order_date DESC
            LIMIT %s
        """
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, (limit,))
                    columns = [desc[0] for desc in cursor.description]
                    return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching recent orders: {e}")
            return []
    
    def create_order(self, customer_id: str, items: List[Dict], product_api, customer_info: Dict = None) -> str:
        """Create a new order with items and optionally create delivery in logistics."""
        order_id = str(uuid.uuid4())
        
        # Calculate total from items
        total_amount = 0.0
        order_items = []
        
        for item in items:
            product = product_api.get_product_by_sku(item['product_sku'])
            if product:
                unit_price = float(product['price'])
                quantity = item['quantity']
                total_amount += unit_price * quantity
                order_items.append({
                    'order_item_id': str(uuid.uuid4()),
                    'product_sku': item['product_sku'],
                    'product_name': product['name'],
                    'category': product.get('category', ''),
                    'quantity': quantity,
                    'unit_price': unit_price
                })
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    # Insert order
                    cursor.execute("""
                        INSERT INTO orders (order_id, customer_id, status, total_amount, currency)
                        VALUES (%s, %s, 'pending', %s, 'EUR')
                    """, (order_id, customer_id, total_amount))
                    
                    # Insert order items with category
                    for oi in order_items:
                        cursor.execute("""
                            INSERT INTO order_items (order_item_id, order_id, product_sku, 
                                                    product_name, category, quantity, unit_price)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (
                            oi['order_item_id'],
                            order_id,
                            oi['product_sku'],
                            oi['product_name'],
                            oi['category'],
                            oi['quantity'],
                            oi['unit_price']
                        ))
                
                conn.commit()
                
                # Create delivery in logistics system if customer info provided
                if customer_info:
                    try:
                        from services.logistics_api import LogisticsAPI
                        logistics_api = LogisticsAPI()
                        
                        delivery_data = {
                            'order_id': order_id,
                            'customer_name': f"{customer_info.get('first_name', '')} {customer_info.get('last_name', '')}".strip(),
                            'address': customer_info.get('address', ''),
                            'city': customer_info.get('city', ''),
                            'postal_code': customer_info.get('postal_code', ''),
                            'country': customer_info.get('country', 'France'),
                            'notes': ''
                        }
                        
                        result = logistics_api.create_delivery(delivery_data)
                        if result:
                            print(f"Delivery created: {result.get('tracking_number')}")
                        else:
                            print("Warning: Could not create delivery in logistics system")
                    except Exception as e:
                        print(f"Warning: Failed to create delivery: {e}")
                
                return order_id
        except Exception as e:
            print(f"Error creating order: {e}")
            raise
    
    def update_order_status(self, order_id: str, status: str) -> bool:
        """Update order status."""
        valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
        if status not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of: {valid_statuses}")
        
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE orders SET status = %s WHERE order_id = %s",
                        (status, order_id)
                    )
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating order status: {e}")
            raise
