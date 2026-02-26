"""
Order Management App - Flask Application (PostgreSQL)
Port: 5002
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-order')

from services.customer_service import CustomerService
from services.order_service import OrderService
from services.search_service import CustomerSearchService
from services.product_api import ProductAPI
from services.nl_query_service import NaturalLanguageQueryService

customer_service = CustomerService()
order_service = OrderService()
search_service = CustomerSearchService()
product_api = ProductAPI()
nl_query_service = NaturalLanguageQueryService()


# ============================================================================
# CUSTOMER ROUTES
# ============================================================================

@app.route('/')
def index():
    """Dashboard - overview of customers and orders."""
    customers_count = customer_service.count_customers()
    orders_count = order_service.count_orders()
    recent_orders = order_service.get_recent_orders(limit=5)
    
    return render_template('index.html',
                         customers_count=customers_count,
                         orders_count=orders_count,
                         recent_orders=recent_orders)


@app.route('/customers')
def customers():
    """List all customers."""
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    customers_list = customer_service.get_all_customers(page=page, per_page=per_page)
    total = customer_service.count_customers()
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('customers/list.html',
                         customers=customers_list,
                         page=page,
                         total_pages=total_pages,
                         total=total)


@app.route('/customers/<customer_id>')
def customer_detail(customer_id):
    """Customer detail page with order history."""
    customer = customer_service.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found', 'error')
        return redirect(url_for('customers'))
    
    orders = order_service.get_orders_by_customer(customer_id)
    
    return render_template('customers/detail.html', customer=customer, orders=orders)


@app.route('/customers/add', methods=['GET', 'POST'])
def add_customer():
    """Add new customer."""
    if request.method == 'POST':
        data = {
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name'],
            'email': request.form['email'],
            'phone': request.form.get('phone', ''),
            'address': request.form.get('address', ''),
            'city': request.form.get('city', ''),
            'country': request.form.get('country', '')
        }
        
        try:
            customer_id = customer_service.create_customer(data)
            flash('Customer created successfully!', 'success')
            return redirect(url_for('customer_detail', customer_id=customer_id))
        except Exception as e:
            flash(f'Error creating customer: {str(e)}', 'error')
    
    return render_template('customers/form.html', customer=None, action='Add')


@app.route('/customers/<customer_id>/edit', methods=['GET', 'POST'])
def edit_customer(customer_id):
    """Edit customer."""
    customer = customer_service.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found', 'error')
        return redirect(url_for('customers'))
    
    if request.method == 'POST':
        data = {
            'first_name': request.form['first_name'],
            'last_name': request.form['last_name'],
            'email': request.form['email'],
            'phone': request.form.get('phone', ''),
            'address': request.form.get('address', ''),
            'city': request.form.get('city', ''),
            'country': request.form.get('country', '')
        }
        
        try:
            customer_service.update_customer(customer_id, data)
            flash('Customer updated successfully!', 'success')
            return redirect(url_for('customer_detail', customer_id=customer_id))
        except Exception as e:
            flash(f'Error updating customer: {str(e)}', 'error')
    
    return render_template('customers/form.html', customer=customer, action='Edit')


@app.route('/customers/search')
def search_customers():
    """Search customers with trigram and vector similarity."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')
    
    results = []
    search_info = {}
    
    if query:
        if search_type == 'trigram':
            results = search_service.trigram_search(query)
            search_info['method'] = 'Trigram Similarity (pg_trgm)'
        elif search_type == 'vector':
            results = search_service.vector_search(query)
            search_info['method'] = 'Vector Search (pgvector)'
        else:
            results = search_service.hybrid_search(query)
            search_info['method'] = 'Hybrid Search (RRF)'
        
        search_info['count'] = len(results)
        search_info['query'] = query
    
    return render_template('customers/search.html',
                         results=results,
                         query=query,
                         search_type=search_type,
                         search_info=search_info)


# ============================================================================
# ORDER ROUTES
# ============================================================================

@app.route('/orders')
def orders():
    """List all orders."""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    per_page = 20
    
    orders_list = order_service.get_all_orders(page=page, per_page=per_page, status=status)
    total = order_service.count_orders(status=status)
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('orders/list.html',
                         orders=orders_list,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         status_filter=status)


@app.route('/orders/<order_id>')
def order_detail(order_id):
    """Order detail page with items."""
    order = order_service.get_order_by_id(order_id)
    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('orders'))
    
    items = order_service.get_order_items(order_id)
    customer = customer_service.get_customer_by_id(order['customer_id'])
    
    return render_template('orders/detail.html', order=order, items=items, customer=customer)


@app.route('/orders/create', methods=['GET', 'POST'])
def create_order():
    """Create new order - select customer and products."""
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        product_skus = request.form.getlist('product_sku')
        quantities = request.form.getlist('quantity')
        
        # Build order items
        items = []
        for sku, qty in zip(product_skus, quantities):
            if sku and int(qty) > 0:
                items.append({'product_sku': sku, 'quantity': int(qty)})
        
        if not items:
            flash('Please add at least one product to the order', 'error')
            return redirect(url_for('create_order'))
        
        try:
            # Get customer info for delivery creation
            customer = customer_service.get_customer_by_id(customer_id)
            
            order_id = order_service.create_order(customer_id, items, product_api, customer_info=customer)
            flash('Order created successfully! Delivery pending dispatch.', 'success')
            return redirect(url_for('order_detail', order_id=order_id))
        except Exception as e:
            flash(f'Error creating order: {str(e)}', 'error')
    
    # Get customers for selection
    all_customers = customer_service.get_all_customers(page=1, per_page=100)
    
    # Get products from Azure SQL
    products = product_api.get_all_products()
    
    return render_template('orders/create.html', customers=all_customers, products=products)


@app.route('/orders/<order_id>/status', methods=['POST'])
def update_order_status(order_id):
    """Update order status."""
    new_status = request.form['status']
    
    try:
        order_service.update_order_status(order_id, new_status)
        flash(f'Order status updated to {new_status}', 'success')
    except Exception as e:
        flash(f'Error updating status: {str(e)}', 'error')
    
    return redirect(url_for('order_detail', order_id=order_id))


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/customers')
def api_customers():
    """API: Get all customers."""
    customers_list = customer_service.get_all_customers(page=1, per_page=100)
    return jsonify(customers_list)


@app.route('/api/customers/search')
def api_search_customers():
    """API: Search customers."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    if search_type == 'trigram':
        results = search_service.trigram_search(query)
    elif search_type == 'vector':
        results = search_service.vector_search(query)
    else:
        results = search_service.hybrid_search(query)
    
    return jsonify({'query': query, 'type': search_type, 'results': results})


@app.route('/api/orders')
def api_orders():
    """API: Get all orders."""
    orders_list = order_service.get_all_orders(page=1, per_page=100)
    return jsonify(orders_list)


@app.route('/api/orders/<order_id>')
def api_order(order_id):
    """API: Get order details."""
    order = order_service.get_order_by_id(order_id)
    if not order:
        return jsonify({'error': 'Order not found'}), 404
    
    order['items'] = order_service.get_order_items(order_id)
    return jsonify(order)


# ============================================================================
# NATURAL LANGUAGE QUERY
# ============================================================================

@app.route('/nl-query', methods=['GET', 'POST'])
def nl_query():
    """Natural Language Query interface - Query database using plain language."""
    result = None
    query = ''
    
    if request.method == 'POST':
        query = request.form.get('query', '').strip()
        if query:
            result = nl_query_service.query(query)
    
    examples = nl_query_service.get_example_queries()
    
    return render_template('nl_query.html', 
                         query=query, 
                         result=result, 
                         examples=examples)


@app.route('/api/nl-query', methods=['POST'])
def api_nl_query():
    """API: Natural Language Query."""
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({'error': 'Query is required'}), 400
    
    result = nl_query_service.query(data['query'])
    return jsonify(result)


if __name__ == '__main__':
    port = int(os.getenv('ORDER_APP_PORT', 5002))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
