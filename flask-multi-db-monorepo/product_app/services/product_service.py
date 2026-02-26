"""
Product Service - Database operations for products (Azure SQL)
Using mssql-python driver with SQL authentication
"""
from mssql_python import connect
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import azure_sql_config
from shared.embeddings import generate_embedding, embedding_to_json


class ProductService:
    """Service for product CRUD operations using Azure SQL with mssql-python."""
    
    def __init__(self):
        self.config = azure_sql_config
    
    def _get_connection(self):
        """Get database connection using mssql-python with SQL authentication."""
        return self.config.get_connection()
    
    def _row_to_dict(self, row, columns) -> Dict[str, Any]:
        """Convert mssql-python row to dictionary."""
        result = {}
        for i, col in enumerate(columns):
            value = row[i]
            if isinstance(value, datetime):
                value = value.isoformat()
            result[col] = value
        return result
    
    def get_all_products(self, page: int = 1, per_page: int = 20) -> List[Dict[str, Any]]:
        """Get paginated list of products."""
        offset = (page - 1) * per_page
        
        query = """
            SELECT sku, name, description, price, currency, tags, stock, category, image_url, created_at
            FROM products
            ORDER BY created_at DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (offset, per_page))
                columns = [col[0] for col in cursor.description]
                return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching products: {e}")
            return []
    
    def count_products(self, category: str = '', search: str = '', stock_filter: str = '') -> int:
        """Count total products with optional filtering."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT COUNT(*) FROM products WHERE 1=1"
                params = []
                
                if category:
                    query += " AND category = ?"
                    params.append(category)
                
                if search:
                    query += " AND (name LIKE ? OR description LIKE ? OR sku LIKE ?)"
                    search_param = f"%{search}%"
                    params.extend([search_param, search_param, search_param])
                
                if stock_filter == 'low':
                    query += " AND stock < 50"
                elif stock_filter == 'high':
                    query += " AND stock >= 50"
                
                cursor.execute(query, params)
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error counting products: {e}")
            return 0
    
    def get_categories(self) -> List[str]:
        """Get all unique categories."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT DISTINCT category FROM products WHERE category IS NOT NULL AND category <> '' ORDER BY category")
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching categories: {e}")
            return []
    
    def get_products_filtered(self, page: int = 1, per_page: int = 20, category: str = '', 
                               search: str = '', min_price: float = None, max_price: float = None,
                               sort: str = 'created_at', order: str = 'DESC',
                               stock_filter: str = '') -> List[Dict[str, Any]]:
        """Get filtered and sorted products."""
        offset = (page - 1) * per_page
        
        query = """
            SELECT sku, name, description, price, currency, tags, stock, category, image_url, created_at
            FROM products
            WHERE 1=1
        """
        params = []
        
        if category:
            query += " AND category = ?"
            params.append(category)
        
        if search:
            query += " AND (name LIKE ? OR description LIKE ? OR sku LIKE ?)"
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        if min_price is not None:
            query += " AND price >= ?"
            params.append(min_price)
        
        if max_price is not None:
            query += " AND price <= ?"
            params.append(max_price)
        
        if stock_filter == 'low':
            query += " AND stock < 50"
        elif stock_filter == 'high':
            query += " AND stock >= 50"
        
        # Validate sort column
        valid_sorts = ['created_at', 'name', 'price', 'stock', 'category']
        if sort not in valid_sorts:
            sort = 'created_at'
        
        order = 'DESC' if order.upper() == 'DESC' else 'ASC'
        query += f" ORDER BY {sort} {order}"
        query += " OFFSET ? ROWS FETCH NEXT ? ROWS ONLY"
        params.extend([offset, per_page])
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                return [self._row_to_dict(row, columns) for row in cursor.fetchall()]
        except Exception as e:
            print(f"Error fetching filtered products: {e}")
            return []
    
    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Get product by SKU."""
        query = """
            SELECT sku, name, description, price, currency, tags, stock, category, image_url, created_at
            FROM products
            WHERE sku = ?
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (sku,))
                columns = [col[0] for col in cursor.description]
                row = cursor.fetchone()
                if row:
                    return self._row_to_dict(row, columns)
                return None
        except Exception as e:
            print(f"Error fetching product: {e}")
            return None
    
    def create_product(self, data: Dict[str, Any]) -> bool:
        """Create a new product with embedding."""
        # Generate embedding for description
        embedding = generate_embedding(data.get('description', ''))
        embedding_json = embedding_to_json(embedding)
        
        query = """
            INSERT INTO products (sku, name, description, price, currency, tags, stock, category, description_embedding, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (
                    data['sku'],
                    data['name'],
                    data['description'],
                    data['price'],
                    data.get('currency', 'EUR'),
                    data.get('tags', ''),
                    data.get('stock', 0),
                    data.get('category', ''),
                    embedding_json,
                    data.get('image_url', None)
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error creating product: {e}")
            raise
    
    def update_product(self, sku: str, data: Dict[str, Any]) -> bool:
        """Update an existing product."""
        # Regenerate embedding if description changed
        embedding = generate_embedding(data.get('description', ''))
        embedding_json = embedding_to_json(embedding)
        
        # Build update query - only update image_url if provided
        if data.get('image_url') is not None:
            query = """
                UPDATE products
                SET name = ?, description = ?, price = ?, currency = ?, 
                    tags = ?, stock = ?, category = ?, description_embedding = ?, image_url = ?
                WHERE sku = ?
            """
            params = (
                data['name'],
                data['description'],
                data['price'],
                data.get('currency', 'EUR'),
                data.get('tags', ''),
                data.get('stock', 0),
                data.get('category', ''),
                embedding_json,
                data['image_url'],
                sku
            )
        else:
            query = """
                UPDATE products
                SET name = ?, description = ?, price = ?, currency = ?, 
                    tags = ?, stock = ?, category = ?, description_embedding = ?
                WHERE sku = ?
            """
            params = (
                data['name'],
                data['description'],
                data['price'],
                data.get('currency', 'EUR'),
                data.get('tags', ''),
                data.get('stock', 0),
                data.get('category', ''),
                embedding_json,
                sku
            )
        
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            print(f"Error updating product: {e}")
            raise
    
    def decrement_stock(self, sku: str, quantity: int) -> bool:
        """Decrease stock for a product by the given quantity."""
        query = """
            UPDATE products
            SET stock = CASE WHEN stock >= ? THEN stock - ? ELSE 0 END
            WHERE sku = ?
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (quantity, quantity, sku))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error decrementing stock for {sku}: {e}")
            return False

    def delete_product(self, sku: str) -> bool:
        """Delete a product."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM products WHERE sku = ?", (sku,))
                conn.commit()
                return True
        except Exception as e:
            print(f"Error deleting product: {e}")
            raise
