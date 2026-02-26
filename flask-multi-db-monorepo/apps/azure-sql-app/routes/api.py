"""
API routes for Azure SQL Flask App using mssql-python driver
"""
from flask import Blueprint, request, jsonify
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))
from shared.database.azure_sql import get_db

api_bp = Blueprint('api', __name__, url_prefix='/api')


@api_bp.route('/products', methods=['GET'])
def list_products():
    """List all products."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sku, name, description, price, currency, tags, stock, category, created_at
            FROM products
            ORDER BY created_at DESC
        """)
        columns = [col[0] for col in cursor.description]
        products = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return jsonify(products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products', methods=['POST'])
def create_product():
    """Create a new product."""
    data = request.json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (sku, name, description, price, currency, tags, stock, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['sku'],
            data['name'],
            data.get('description', ''),
            data['price'],
            data.get('currency', 'EUR'),
            data.get('tags', ''),
            data.get('stock', 0),
            data.get('category', '')
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product created', 'sku': data['sku']}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/<sku>', methods=['GET'])
def get_product(sku):
    """Get a product by SKU."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT sku, name, description, price, currency, tags, stock, category, created_at
            FROM products
            WHERE sku = ?
        """, (sku,))
        columns = [col[0] for col in cursor.description]
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return jsonify(dict(zip(columns, row))), 200
        return jsonify({'error': 'Product not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/<sku>', methods=['PUT'])
def update_product(sku):
    """Update a product."""
    data = request.json
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE products
            SET name = ?, description = ?, price = ?, currency = ?, 
                tags = ?, stock = ?, category = ?
            WHERE sku = ?
        """, (
            data['name'],
            data.get('description', ''),
            data['price'],
            data.get('currency', 'EUR'),
            data.get('tags', ''),
            data.get('stock', 0),
            data.get('category', ''),
            sku
        ))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product updated', 'sku': sku}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/<sku>', methods=['DELETE'])
def delete_product(sku):
    """Delete a product."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM products WHERE sku = ?", (sku,))
        conn.commit()
        conn.close()
        return jsonify({'message': 'Product deleted', 'sku': sku}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/products/search', methods=['GET'])
def search_products():
    """Search products by keyword."""
    query = request.args.get('q', '')
    if not query:
        return jsonify({'error': 'Query parameter q is required'}), 400
    
    try:
        conn = get_db()
        cursor = conn.cursor()
        pattern = f'%{query}%'
        cursor.execute("""
            SELECT sku, name, description, price, currency, tags, stock, category
            FROM products
            WHERE name LIKE ? OR description LIKE ? OR tags LIKE ?
            ORDER BY name
        """, (pattern, pattern, pattern))
        columns = [col[0] for col in cursor.description]
        products = [dict(zip(columns, row)) for row in cursor.fetchall()]
        conn.close()
        return jsonify(products), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500