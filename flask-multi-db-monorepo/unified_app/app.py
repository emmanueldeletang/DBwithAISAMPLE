"""
Unified Multi-Database Demo Application
Combines Product, Order, and Logistics functionality with Entra ID authentication
"""
import os
import sys
from functools import wraps

# Add parent directory for shared imports and sibling app imports
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, g
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv
from unified_app.translations import get_translation, LANGUAGES, DEFAULT_LANG

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'unified-app-secret-key-change-in-production')

# Server-side sessions (auth code flow dict is too large for cookies)
app.config['SESSION_TYPE'] = 'filesystem'
try:
    from flask_session import Session
    Session(app)
except ImportError:
    pass  # Falls back to default cookie-based sessions

# Required for url_for(... _external=True) to produce https behind a reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# ============================================================================
# Authentication helpers
# ============================================================================

def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('user'):
            return redirect(url_for('login'))
        g.user = session['user']
        return f(*args, **kwargs)
    return decorated_function


# ============================================================================
# Import Services
# ============================================================================

# Product Services (Azure SQL)
from product_app.services.product_service import ProductService
from product_app.services.search_service import ProductSearchService
from product_app.services.image_service import ImageService
from shared.config import azure_sql_config

# Order Services (PostgreSQL)
from order_app.services.customer_service import CustomerService
from order_app.services.order_service import OrderService
from order_app.services.search_service import CustomerSearchService
from order_app.services.nl_query_service import NaturalLanguageQueryService as PostgresNLQuery

# Logistics Services (MongoDB)
from logistics_app.services.partner_service import PartnerService
from logistics_app.services.delivery_service import DeliveryService
from logistics_app.services.nl_query_service import NLQueryService as MongoNLQuery
from logistics_app.services.login_audit_service import LoginAuditService
from unified_app.services.user_service import UserService
from unified_app.services.inventory_agent import InventoryAgent
from unified_app.services.activity_tracking_service import ActivityTrackingService

# Product NL Query Service (Azure SQL)
from product_app.services.nl_query_service import NLQueryService as AzureSQLNLQuery

# Cosmos DB NoSQL NL Query Service (Activity Tracking)
from unified_app.services.cosmos_nl_query_service import CosmosNLQueryService

# Azure Translator Service (dynamic DB content translation)
from unified_app.services.translation_service import AzureTranslatorService

# Initialize services
product_service = ProductService()
product_search_service = ProductSearchService()
image_service = ImageService()

customer_service = CustomerService()
order_service = OrderService()
customer_search_service = CustomerSearchService()
postgres_nl_query = PostgresNLQuery()

partner_service = PartnerService()
delivery_service = DeliveryService()
mongo_nl_query = MongoNLQuery()
azuresql_nl_query = AzureSQLNLQuery()
cosmos_nl_query = CosmosNLQueryService()
login_audit = LoginAuditService()
user_service = UserService()
user_service.ensure_table()
inventory_agent = InventoryAgent()
activity_tracker = ActivityTrackingService()
translator = AzureTranslatorService()


# ============================================================================
# Activity Tracking – log every page view automatically
# ============================================================================

@app.after_request
def track_user_activity(response):
    """Automatically log page views to Cosmos DB for authenticated users."""
    try:
        email = session.get('user_email')
        if email and request.endpoint and response.status_code < 400:
            # Skip static files and API-only endpoints
            if not request.path.startswith('/static'):
                # Determine action from HTTP method
                method = request.method
                if method == 'GET':
                    action = 'view'
                elif method == 'POST':
                    action = 'submit'
                elif method == 'PUT' or method == 'PATCH':
                    action = 'update'
                elif method == 'DELETE':
                    action = 'delete'
                else:
                    action = method.lower()
                activity_tracker.track(
                    email=email,
                    page=request.path,
                    action=action,
                    details=f"{method} {request.endpoint}"
                )
    except Exception:
        pass  # Never let tracking break the app
    return response


# ============================================================================
# i18n – language handling
# ============================================================================

@app.before_request
def set_language():
    """Set g.lang from session (default: en)."""
    g.lang = session.get('lang', DEFAULT_LANG)


def _(key: str) -> str:
    """Translate *key* using the current request language."""
    return get_translation(key, getattr(g, 'lang', DEFAULT_LANG))


# Make _() and language info available in every Jinja2 template
app.jinja_env.globals['_'] = _
app.jinja_env.globals['LANGUAGES'] = LANGUAGES


def _translate_filter(text):
    """Jinja2 filter: translate DB content to the user's current language."""
    if not text:
        return text or ''
    lang = getattr(g, 'lang', DEFAULT_LANG)
    if lang == 'en':
        return text
    return translator.translate(str(text), lang)


app.jinja_env.filters['translate'] = _translate_filter


# ============================================================================
# Context Processor - Make user available in all templates
# ============================================================================

@app.context_processor
def inject_user():
    """Inject user and language info into all templates."""
    return dict(
        current_user=getattr(g, 'user', None),
        current_lang=getattr(g, 'lang', DEFAULT_LANG),
    )


# ============================================================================
# Authentication Routes
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page with email and password."""
    if session.get('user'):
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter both email and password.', 'warning')
            return render_template('auth/login.html')

        user = user_service.authenticate(email, password)
        if user:
            session['user'] = {
                'name': user['username'],
                'email': user['email'],
                'user_id': user['user_id']
            }
            session['user_email'] = user['email']
            # Track login activity
            activity_tracker.track(
                email=user['email'],
                page='/login',
                action='login',
                details=f"User {user['username']} logged in"
            )
            # Audit log
            login_audit.log_login(
                email=user['email'],
                ip=request.remote_addr or 'unknown',
                method='password',
                user_agent=request.headers.get('User-Agent', '')
            )
            flash(f"Welcome, {user['username']}!", 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password.', 'error')

    return render_template('auth/login.html')


@app.route('/logout')
def logout():
    """Logout user."""
    email = session.get('user_email', '')
    if email:
        activity_tracker.track(
            email=email,
            page='/logout',
            action='logout',
            details='User logged out'
        )
        login_audit.log_login(
            email=email,
            ip=request.remote_addr or 'unknown',
            method='logout',
            user_agent=request.headers.get('User-Agent', '')
        )
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('login'))


@app.route('/set-language/<lang>')
def set_language_route(lang):
    """Switch UI language. Works before or after login."""
    if lang in LANGUAGES:
        session['lang'] = lang
    next_url = request.args.get('next') or request.referrer or url_for('login')
    return redirect(next_url)


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@app.route('/users')
@login_required
def users_list():
    """List all users with search and pagination."""
    search = request.args.get('search', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 20

    users, total = user_service.search_users(search=search, page=page, per_page=per_page)
    total_pages = (total + per_page - 1) // per_page if total else 0

    return render_template('users/list.html',
                           users=users,
                           total=total,
                           page=page,
                           total_pages=total_pages,
                           search=search)


@app.route('/users/create', methods=['GET', 'POST'])
@login_required
def user_create():
    """Create a new user."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        if not username or not email or not password:
            flash('All fields are required.', 'warning')
            return render_template('users/form.html', user=None, action='Create')

        try:
            user_service.create_user(username, email, password)
            flash(f'User "{username}" created successfully!', 'success')
            return redirect(url_for('users_list'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'Error creating user: {e}', 'error')

    return render_template('users/form.html', user=None, action='Create')


@app.route('/users/<user_id>/edit', methods=['GET', 'POST'])
@login_required
def user_edit(user_id):
    """Edit a user."""
    user = user_service.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('users_list'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        is_active = 'is_active' in request.form

        if not username or not email:
            flash('Username and email are required.', 'warning')
            return render_template('users/form.html', user=user, action='Edit')

        try:
            user_service.update_user(user_id, username, email, is_active)
            flash(f'User "{username}" updated successfully!', 'success')
            return redirect(url_for('users_list'))
        except ValueError as e:
            flash(str(e), 'error')
        except Exception as e:
            flash(f'Error updating user: {e}', 'error')

    return render_template('users/form.html', user=user, action='Edit')


@app.route('/users/<user_id>/password', methods=['GET', 'POST'])
@login_required
def user_password(user_id):
    """Change a user's password (own account only)."""
    current_user_id = session.get('user', {}).get('user_id', '')
    if str(user_id) != str(current_user_id):
        flash('You can only change your own password.', 'error')
        return redirect(url_for('users_list'))

    user = user_service.get_user_by_id(user_id)
    if not user:
        flash('User not found.', 'error')
        return redirect(url_for('users_list'))

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not new_password:
            flash('Please enter a new password.', 'warning')
        elif new_password != confirm_password:
            flash('Passwords do not match.', 'error')
        else:
            if user_service.change_password(user_id, new_password):
                flash(f'Password changed for {user["username"]}.', 'success')
                return redirect(url_for('users_list'))
            else:
                flash('Failed to change password.', 'error')

    return render_template('users/password.html', user=user)


@app.route('/users/<user_id>/delete', methods=['POST'])
@login_required
def user_delete(user_id):
    """Delete a user."""
    if user_service.delete_user(user_id):
        flash('User deleted.', 'success')
    else:
        flash('Failed to delete user.', 'error')
    return redirect(url_for('users_list'))


# ============================================================================
# AUDIT LOG
# ============================================================================

@app.route('/audit')
@login_required
def audit_log():
    """Audit log page with statistics."""
    filter_email = request.args.get('email', '')
    filter_method = request.args.get('method', '')
    filter_ip = request.args.get('ip', '')

    # Get recent logs (potentially filtered)
    if filter_email:
        logs = login_audit.get_logins_by_email(filter_email, limit=100)
    else:
        logs = login_audit.get_recent_logins(limit=100)

    # Apply additional filters client-side (method / ip)
    if filter_method:
        logs = [l for l in logs if l.get('method') == filter_method]
    if filter_ip:
        logs = [l for l in logs if l.get('ip') == filter_ip]

    stats = login_audit.get_statistics()

    return render_template('audit/log.html',
                         logs=logs,
                         stats=stats,
                         filter_email=filter_email,
                         filter_method=filter_method,
                         filter_ip=filter_ip)


# ============================================================================
# ACTIVITY LOG (Cosmos DB NoSQL)
# ============================================================================

@app.route('/activities')
@login_required
def activity_log():
    """Activity log page – filter by day and/or email."""
    from datetime import datetime as dt, timezone as tz

    filter_email = request.args.get('email', '')
    filter_date = request.args.get('date', dt.now(tz.utc).strftime('%Y-%m-%d'))

    documents = []
    total_actions = 0
    try:
        if filter_email:
            # Single user for a specific day
            doc = activity_tracker.get_activities_for_day(filter_email, filter_date)
            if doc:
                documents = [doc]
        else:
            # All users for that day (cross-partition)
            documents = activity_tracker.get_all_activities_for_day(filter_date)

        total_actions = sum(len(d.get('activities', [])) for d in documents)
    except Exception as exc:
        flash(f'Error loading activities: {exc}', 'error')

    # Get list of known emails for the filter dropdown
    try:
        known_emails = activity_tracker.get_distinct_emails()
    except Exception:
        known_emails = []

    return render_template('audit/activities.html',
                           documents=documents,
                           total_actions=total_actions,
                           filter_email=filter_email,
                           filter_date=filter_date,
                           known_emails=known_emails)


# ============================================================================
# Main Dashboard
# ============================================================================

@app.route('/')
@login_required
def index():
    """Main dashboard."""
    try:
        # Get counts from all databases
        products_count = product_service.count_products()
    except Exception:
        products_count = 0
    
    try:
        customers_count = customer_service.count_customers()
    except Exception:
        customers_count = 0
    
    try:
        orders_count = order_service.count_orders()
    except Exception:
        orders_count = 0
    
    try:
        deliveries_count = delivery_service.count_deliveries()
    except Exception:
        deliveries_count = 0
    
    try:
        pending_deliveries = delivery_service.count_by_status('pending')
    except Exception:
        pending_deliveries = 0
    
    try:
        partners_count = partner_service.count_partners()
    except Exception:
        partners_count = 0
    
    # Build stats dict for template
    stats = {
        'products': products_count,
        'customers': customers_count,
        'orders': orders_count,
        'deliveries': deliveries_count,
        'pending_deliveries': pending_deliveries,
        'partners': partners_count
    }
    
    return render_template('dashboard.html', stats=stats)


# ============================================================================
# PRODUCTS (Azure SQL)
# ============================================================================

@app.route('/products')
@login_required
def products():
    """Product catalog with filtering."""
    page = request.args.get('page', 1, type=int)
    per_page = 12
    category = request.args.get('category', '')
    search = request.args.get('search', '')
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'created_at')
    order = request.args.get('order', 'DESC')
    stock_filter = request.args.get('stock_filter', '')
    
    products_list = product_service.get_products_filtered(
        page=page, per_page=per_page, category=category,
        search=search, min_price=min_price, max_price=max_price,
        sort=sort, order=order, stock_filter=stock_filter
    )
    total = product_service.count_products(category=category, search=search, stock_filter=stock_filter)
    total_pages = (total + per_page - 1) // per_page
    categories = product_service.get_categories()
    
    return render_template('products/list.html',
                         products=products_list,
                         page=page,
                         total_pages=total_pages,
                         total=total,
                         categories=categories,
                         current_category=category,
                         search=search,
                         min_price=min_price,
                         max_price=max_price,
                         sort=sort,
                         order=order,
                         stock_filter=stock_filter)


@app.route('/products/<product_id>')
@login_required
def product_detail(product_id):
    """Product detail page."""
    product = product_service.get_product_by_sku(product_id)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products'))
    
    return render_template('products/detail.html', product=product)


@app.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add new product."""
    if request.method == 'POST':
        data = {
            'sku': request.form['sku'],
            'name': request.form['name'],
            'description': request.form['description'],
            'price': float(request.form['price']),
            'category': request.form.get('category', ''),
            'stock': int(request.form.get('stock_quantity', 0))
        }
        
        try:
            # Handle image: upload or AI-generate
            image_url = None
            image_option = request.form.get('image_option', 'none')
            
            if image_option == 'upload' and 'image_file' in request.files:
                file = request.files['image_file']
                if file and file.filename:
                    image_url = image_service.upload_product_image(data['sku'], file)
                    flash('Image uploaded successfully!', 'info')
            elif image_option == 'generate':
                image_url = image_service.generate_product_image(
                    name=data['name'],
                    description=data['description'],
                    category=data.get('category', ''),
                    sku=data['sku']
                )
                flash('Image generated with DALL-E!', 'info')
            
            data['image_url'] = image_url
            product_service.create_product(data)
            activity_tracker.track(
                email=session.get('user_email', ''),
                page='/products/add',
                action='create_product',
                details=f"Created product {data['sku']} - {data['name']}"
            )
            flash(f'Product "{data["name"]}" created successfully!', 'success')
            return redirect(url_for('product_detail', product_id=data['sku']))
        except Exception as e:
            flash(f'Error creating product: {str(e)}', 'error')
    
    return render_template('products/form.html', product=None)


@app.route('/products/<product_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit product."""
    product = product_service.get_product_by_sku(product_id)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('products'))
    
    if request.method == 'POST':
        data = {
            'name': request.form['name'],
            'description': request.form['description'],
            'price': float(request.form['price']),
            'category': request.form.get('category', ''),
            'stock': int(request.form.get('stock_quantity', 0))
        }
        
        try:
            # Handle image: upload or AI-generate
            image_option = request.form.get('image_option', 'none')
            
            if image_option == 'upload' and 'image_file' in request.files:
                file = request.files['image_file']
                if file and file.filename:
                    data['image_url'] = image_service.upload_product_image(product_id, file)
                    flash('Image uploaded successfully!', 'info')
            elif image_option == 'generate':
                data['image_url'] = image_service.generate_product_image(
                    name=data['name'],
                    description=data['description'],
                    category=data.get('category', ''),
                    sku=product_id
                )
                flash('Image generated with DALL-E!', 'info')
            
            product_service.update_product(product_id, data)
            activity_tracker.track(
                email=session.get('user_email', ''),
                page=f'/products/{product_id}/edit',
                action='update_product',
                details=f"Updated product {product_id}"
            )
            flash('Product updated successfully!', 'success')
            return redirect(url_for('product_detail', product_id=product_id))
        except Exception as e:
            flash(f'Error updating product: {str(e)}', 'error')
    
    return render_template('products/form.html', product=product)


@app.route('/products/<product_id>/delete', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete product."""
    try:
        product_service.delete_product(product_id)
        activity_tracker.track(
            email=session.get('user_email', ''),
            page=f'/products/{product_id}/delete',
            action='delete_product',
            details=f"Deleted product {product_id}"
        )
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'error')
    
    return redirect(url_for('products'))
@app.route('/products/search')
@login_required
def search_products():
    """Search products."""
    query = request.args.get('q', '')
    limit = request.args.get('limit', 10, type=int)
    
    results = []
    
    if query:
        try:
            results = product_search_service.vector_search(query, limit=limit)
        except Exception as e:
            flash(f'Search error: {str(e)}', 'error')
    
    return render_template('products/search.html',
                         results=results,
                         query=query,
                         limit=limit)


# ============================================================================
# ORDERS (PostgreSQL)
# ============================================================================

@app.route('/orders')
@login_required
def orders():
    """Order list."""
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
@login_required
def order_detail(order_id):
    """Order detail page."""
    order = order_service.get_order_by_id(order_id)
    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('orders'))
    
    order_items = order_service.get_order_items(order_id)
    customer = customer_service.get_customer_by_id(order['customer_id'])
    
    # Get delivery info from MongoDB
    delivery = delivery_service.get_by_order_id(order_id)
    
    return render_template('orders/detail.html',
                         order=order,
                         order_items=order_items,
                         customer=customer,
                         delivery=delivery)


@app.route('/orders/<order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    """Update order status."""
    new_status = request.form.get('status')
    if new_status:
        try:
            order_service.update_order_status(order_id, new_status)
            activity_tracker.track(
                email=session.get('user_email', ''),
                page=f'/orders/{order_id}/status',
                action='update_order_status',
                details=f"Changed order {order_id} status to {new_status}"
            )
            flash(f'Order status updated to {new_status}', 'success')
        except Exception as e:
            flash(f'Error updating status: {str(e)}', 'error')
    return redirect(url_for('order_detail', order_id=order_id))


@app.route('/orders/create', methods=['GET', 'POST'])
@login_required
def create_order():
    """Create new order."""
    if request.method == 'POST':
        customer_id = request.form['customer_id']
        product_skus = request.form.getlist('product_sku')
        quantities = request.form.getlist('quantity')
        
        items = []
        for sku, qty in zip(product_skus, quantities):
            if sku and int(qty) > 0:
                items.append({'product_sku': sku, 'quantity': int(qty)})
        
        if not items:
            flash('Please add at least one product', 'error')
            return redirect(url_for('create_order'))
        
        try:
            # Get customer info for delivery
            customer = customer_service.get_customer_by_id(customer_id)
            
            # Create order in PostgreSQL
            order_id = order_service.create_order(customer_id, items, 
                                                  ProductAPIInternal(), 
                                                  customer_info=None)  # Don't use built-in logistics API
            activity_tracker.track(
                email=session.get('user_email', ''),
                page='/orders/create',
                action='create_order',
                details=f"Created order {order_id} for customer {customer_id}"
            )
            
            # Decrement stock in Azure SQL for each ordered product
            for item in items:
                product_service.decrement_stock(item['product_sku'], item['quantity'])
            
            # Create delivery in MongoDB for dispatch
            if customer:
                try:
                    delivery_data = {
                        'order_id': order_id,
                        'customer_name': f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip(),
                        'address': customer.get('address', '') or f"{customer.get('city', '')}, {customer.get('country', '')}",
                        'city': customer.get('city', ''),
                        'postal_code': customer.get('postal_code', ''),
                        'country': customer.get('country', 'France'),
                        'notes': f"Order {order_id[:8]}..."
                    }
                    delivery_id = delivery_service.create_delivery(delivery_data)
                    flash(f'Order created successfully! Delivery {delivery_id} added to dispatch.', 'success')
                except Exception as e:
                    flash(f'Order created but delivery creation failed: {str(e)}', 'warning')
            else:
                flash('Order created successfully!', 'success')
            
            return redirect(url_for('order_detail', order_id=order_id))
        except Exception as e:
            flash(f'Error creating order: {str(e)}', 'error')
    
    customers = customer_service.get_all_customers(page=1, per_page=100)
    products_list = product_service.get_all_products(page=1, per_page=100)
    
    return render_template('orders/create.html',
                         customers=customers,
                         products=products_list)


class ProductAPIInternal:
    """Internal product API that directly uses the service."""
    def get_product_by_sku(self, sku):
        return product_service.get_product_by_sku(sku)
    
    def get_all_products(self):
        return product_service.get_all_products(page=1, per_page=100)


# ============================================================================
# CUSTOMERS (PostgreSQL)
# ============================================================================

@app.route('/customers')
@login_required
def customers():
    """Customer list."""
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
@login_required
def customer_detail(customer_id):
    """Customer detail page."""
    customer = customer_service.get_customer_by_id(customer_id)
    if not customer:
        flash('Customer not found', 'error')
        return redirect(url_for('customers'))
    
    customer_orders = order_service.get_orders_by_customer(customer_id)
    total_spent = sum(float(o.get('total_amount', 0)) for o in customer_orders)
    
    return render_template('customers/detail.html',
                         customer=customer,
                         orders=customer_orders,
                         total_spent=total_spent)


@app.route('/customers/add', methods=['GET', 'POST'])
@login_required
def add_customer():
    """Add a new customer."""
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
@login_required
def edit_customer(customer_id):
    """Edit an existing customer."""
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


@app.route('/customers/<customer_id>/delete', methods=['POST'])
@login_required
def delete_customer(customer_id):
    """Delete a customer."""
    try:
        customer_service.delete_customer(customer_id)
        flash('Customer deleted successfully.', 'success')
    except Exception as e:
        flash(f'Error deleting customer: {str(e)}', 'error')
    return redirect(url_for('customers'))


@app.route('/customers/search')
@login_required
def search_customers():
    """Search customers with trigram, vector, or hybrid similarity."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')

    results = []
    search_info = {}

    if query:
        if search_type == 'trigram':
            results = customer_search_service.trigram_search(query)
            search_info['method'] = 'Trigram Similarity (pg_trgm)'
        elif search_type == 'vector':
            results = customer_search_service.vector_search(query)
            search_info['method'] = 'Vector Search (pgvector)'
        else:
            results = customer_search_service.hybrid_search(query)
            search_info['method'] = 'Hybrid Search (RRF)'

        search_info['count'] = len(results)
        search_info['query'] = query

    return render_template('customers/list.html',
                         customers=results if query else customer_service.get_all_customers(page=1, per_page=20),
                         page=1,
                         total_pages=1 if query else (customer_service.count_customers() + 19) // 20,
                         total=len(results) if query else customer_service.count_customers(),
                         search_query=query,
                         search_type=search_type,
                         search_info=search_info)


@app.route('/api/customers/search')
@login_required
def api_search_customers():
    """API: Search customers using similarity search."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')

    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400

    if search_type == 'trigram':
        results = customer_search_service.trigram_search(query)
    elif search_type == 'vector':
        results = customer_search_service.vector_search(query)
    else:
        results = customer_search_service.hybrid_search(query)

    return jsonify({'query': query, 'type': search_type, 'results': results})


# ============================================================================
# DELIVERIES (MongoDB)
# ============================================================================

@app.route('/deliveries')
@login_required
def deliveries():
    """Delivery list - shows deliveries with partners assigned."""
    status_filter = request.args.get('status', '')
    deliveries_list = delivery_service.get_assigned_deliveries(status=status_filter)
    
    # Enrich deliveries with partner names
    partners_cache = {}
    for delivery in deliveries_list:
        partner_id = delivery.get('partner_id')
        if partner_id:
            if partner_id not in partners_cache:
                partner = partner_service.get_partner_by_id(partner_id)
                partners_cache[partner_id] = partner.get('name') if partner else None
            delivery['partner_name'] = partners_cache[partner_id]
        else:
            delivery['partner_name'] = None
    
    # Count unassigned for dispatch badge
    unassigned_count = len(delivery_service.get_unassigned_deliveries())
    
    return render_template('deliveries/list.html',
                         deliveries=deliveries_list,
                         status_filter=status_filter,
                         unassigned_count=unassigned_count)


@app.route('/deliveries/<delivery_id>')
@login_required
def delivery_detail(delivery_id):
    """Delivery detail page."""
    delivery = delivery_service.get_delivery_by_id(delivery_id)
    if not delivery:
        flash('Delivery not found', 'error')
        return redirect(url_for('deliveries'))
    
    partner = None
    if delivery.get('partner_id'):
        partner = partner_service.get_partner_by_id(delivery['partner_id'])
    
    return render_template('deliveries/detail.html',
                         delivery=delivery,
                         partner=partner)


@app.route('/deliveries/dispatch')
@login_required
def dispatch():
    """Dispatch center - deliveries without partner assigned."""
    unassigned_deliveries = delivery_service.get_unassigned_deliveries()
    partners = partner_service.get_all_partners(active_only=True)
    
    return render_template('deliveries/dispatch.html',
                         pending_deliveries=unassigned_deliveries,
                         partners=partners)


@app.route('/deliveries/<delivery_id>/dispatch', methods=['POST'])
@login_required
def dispatch_delivery(delivery_id):
    """Dispatch a delivery to a partner."""
    partner_id = request.form.get('partner_id')
    
    if not partner_id:
        flash('Please select a delivery partner', 'error')
        return redirect(url_for('dispatch'))
    
    try:
        # Get partner name for the flash message
        partner = partner_service.get_partner_by_id(partner_id)
        partner_name = partner.get('name') if partner else partner_id
        
        delivery_service.assign_partner(delivery_id, partner_id)
        delivery_service.update_status(delivery_id, 'picked_up', 
                                       f'Dispatched to {partner_name}', 'Warehouse')
        activity_tracker.track(
            email=session.get('user_email', ''),
            page=f'/deliveries/{delivery_id}/dispatch',
            action='dispatch_delivery',
            details=f"Dispatched delivery {delivery_id} to {partner_name}"
        )
        flash(f'Delivery dispatched to {partner_name}!', 'success')
    except Exception as e:
        flash(f'Error dispatching: {str(e)}', 'error')
    
    return redirect(url_for('dispatch'))


@app.route('/track')
def track():
    """Public tracking page (no login required)."""
    tracking_number = request.args.get('tracking', '')
    delivery = None
    
    if tracking_number:
        # Try by tracking number first
        delivery = delivery_service.get_by_tracking_number(tracking_number)
        # If not found, try by order ID
        if not delivery:
            delivery = delivery_service.get_by_order_id(tracking_number)
    
    return render_template('deliveries/track.html',
                         tracking_number=tracking_number,
                         delivery=delivery)


@app.route('/deliveries/<delivery_id>/status', methods=['POST'])
@login_required
def update_delivery_status(delivery_id):
    """Update delivery status."""
    new_status = request.form.get('status')
    if new_status:
        try:
            delivery_service.update_status(delivery_id, new_status)
            flash(f'Delivery status updated to {new_status}', 'success')
        except Exception as e:
            flash(f'Error updating status: {str(e)}', 'error')
    return redirect(url_for('delivery_detail', delivery_id=delivery_id))


# ============================================================================
# PARTNERS (MongoDB)
# ============================================================================

@app.route('/partners')
@login_required
def partners():
    """Partner list with delivery stats."""
    partners_list = partner_service.get_all_partners()
    
    # Calculate delivery stats for each partner
    for partner in partners_list:
        partner_id = partner.get('partner_id') or partner.get('_id')
        partner_deliveries = delivery_service.get_deliveries_by_partner(partner_id)
        
        total = len(partner_deliveries)
        completed = sum(1 for d in partner_deliveries if d.get('status') == 'delivered')
        active = sum(1 for d in partner_deliveries if d.get('status') in ['pending', 'picked_up', 'in_transit', 'out_for_delivery'])
        
        partner['total_deliveries'] = total
        partner['active_deliveries'] = active
        partner['success_rate'] = round((completed / total * 100)) if total > 0 else 0
    
    return render_template('partners/list.html', partners=partners_list)


@app.route('/partners/<partner_id>')
@login_required
def partner_detail(partner_id):
    """Partner detail page."""
    partner = partner_service.get_partner_by_id(partner_id)
    if not partner:
        flash('Partner not found', 'error')
        return redirect(url_for('partners'))
    
    partner_deliveries = delivery_service.get_deliveries_by_partner(partner_id)
    
    # Calculate stats
    total = len(partner_deliveries)
    completed = sum(1 for d in partner_deliveries if d.get('status') == 'delivered')
    failed = sum(1 for d in partner_deliveries if d.get('status') == 'failed')
    in_progress = total - completed - failed
    
    stats = {
        'total': total,
        'completed': completed,
        'failed': failed,
        'in_progress': in_progress
    }
    
    return render_template('partners/detail.html',
                         partner=partner,
                         deliveries=partner_deliveries,
                         stats=stats)


@app.route('/partners/add', methods=['GET', 'POST'])
@login_required
def add_partner():
    """Create a new partner."""
    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'contact_email': request.form.get('contact_email', '').strip(),
            'contact_phone': request.form.get('contact_phone', '').strip(),
            'service_areas': [a.strip() for a in request.form.get('service_areas', '').split(',') if a.strip()],
            'vehicle_types': [v.strip() for v in request.form.getlist('vehicle_types') if v.strip()],
            'active': request.form.get('active') == 'on',
        }
        if not data['name'] or not data['contact_email']:
            flash('Name and email are required.', 'error')
            return render_template('partners/form.html', partner=data, is_edit=False)
        try:
            partner_id = partner_service.create_partner(data)
            flash(f'Partner created (ID: {partner_id}).', 'success')
            return redirect(url_for('partners'))
        except Exception as e:
            flash(f'Error creating partner: {e}', 'error')
            return render_template('partners/form.html', partner=data, is_edit=False)

    return render_template('partners/form.html', partner={}, is_edit=False)


@app.route('/partners/<partner_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_partner(partner_id):
    """Edit an existing partner."""
    partner = partner_service.get_partner_by_id(partner_id)
    if not partner:
        flash('Partner not found.', 'error')
        return redirect(url_for('partners'))

    if request.method == 'POST':
        data = {
            'name': request.form.get('name', '').strip(),
            'contact_email': request.form.get('contact_email', '').strip(),
            'contact_phone': request.form.get('contact_phone', '').strip(),
            'service_areas': [a.strip() for a in request.form.get('service_areas', '').split(',') if a.strip()],
            'vehicle_types': [v.strip() for v in request.form.getlist('vehicle_types') if v.strip()],
            'active': request.form.get('active') == 'on',
        }
        if not data['name'] or not data['contact_email']:
            flash('Name and email are required.', 'error')
            data['partner_id'] = partner_id
            return render_template('partners/form.html', partner=data, is_edit=True)
        try:
            partner_service.update_partner(partner_id, data)
            flash('Partner updated.', 'success')
            return redirect(url_for('partner_detail', partner_id=partner_id))
        except Exception as e:
            flash(f'Error updating partner: {e}', 'error')
            data['partner_id'] = partner_id
            return render_template('partners/form.html', partner=data, is_edit=True)

    return render_template('partners/form.html', partner=partner, is_edit=True)


@app.route('/partners/<partner_id>/delete', methods=['POST'])
@login_required
def delete_partner(partner_id):
    """Delete a partner."""
    try:
        partner_service.delete_partner(partner_id)
        flash('Partner deleted.', 'success')
    except Exception as e:
        flash(f'Error deleting partner: {e}', 'error')
    return redirect(url_for('partners'))


@app.route('/partners/search')
@login_required
def search_partners():
    """Search partners."""
    query = request.args.get('q', '').strip()
    results = []
    if query:
        results = partner_service.search_partners(query)
    return render_template('partners/search.html', query=query, results=results)


# ============================================================================
# AI / NATURAL LANGUAGE QUERIES
# ============================================================================

@app.route('/ask', methods=['GET', 'POST'])
@login_required
def ask_question():
    """Natural language query interface for PostgreSQL, MongoDB, and Azure SQL."""
    result = None
    question = ''
    error = None
    database = 'postgres'  # Default to PostgreSQL
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        database = request.form.get('database', 'postgres')
        
        if question:
            try:
                if database == 'mongodb':
                    result = mongo_nl_query.ask(question)
                elif database == 'azuresql':
                    result = azuresql_nl_query.query(question)
                elif database == 'cosmosdb':
                    result = cosmos_nl_query.query(question)
                else:
                    result = postgres_nl_query.query(question)
                
                if not result.get('success', False):
                    error = result.get('error', 'Unknown error')
            except Exception as e:
                error = str(e)
    
    # Get suggested questions for all databases
    postgres_suggestions = postgres_nl_query.get_example_queries()
    mongo_suggestions = mongo_nl_query.get_suggested_questions()
    azuresql_suggestions = azuresql_nl_query.get_suggested_questions()
    cosmos_suggestions = cosmos_nl_query.get_suggested_questions()
    
    return render_template('ask.html',
                         question=question,
                         result=result,
                         error=error,
                         database=database,
                         postgres_suggestions=postgres_suggestions,
                         mongo_suggestions=mongo_suggestions,
                         azuresql_suggestions=azuresql_suggestions,
                         cosmos_suggestions=cosmos_suggestions)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/products')
@login_required
def api_products():
    """API: Get all products."""
    products_list = product_service.get_all_products(page=1, per_page=100)
    return jsonify(products_list)


@app.route('/api/products/<sku>')
@login_required
def api_product(sku):
    """API: Get product by SKU."""
    product = product_service.get_product_by_sku(sku)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(product)


@app.route('/api/products/<sku>/image')
def api_product_image(sku):
    """API: Proxy product image from private blob storage."""
    from azure.storage.blob import BlobServiceClient
    from flask import Response
    
    connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    container_name = os.getenv('AZURE_STORAGE_CONTAINER', 'product-images')
    
    if not connection_string:
        account_name = os.getenv('AZURE_STORAGE_ACCOUNT')
        account_key = os.getenv('AZURE_STORAGE_KEY')
        if not account_name or not account_key:
            return '', 404
        account_url = f"https://{account_name}.blob.core.windows.net"
        blob_service_client = BlobServiceClient(account_url, credential=account_key)
    else:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    
    blob_name = f"products/{sku.lower()}.png"
    
    try:
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        # Download blob data
        blob_data = blob_client.download_blob().readall()
        
        return Response(
            blob_data,
            mimetype='image/png',
            headers={
                'Cache-Control': 'public, max-age=86400',  # Cache for 1 day
                'Content-Disposition': f'inline; filename="{sku}.png"'
            }
        )
    except Exception:
        return '', 404


@app.route('/api/products/<sku>/generate-image', methods=['POST'])
@login_required
def api_generate_image(sku):
    """API: Generate image for a product using DALL-E."""
    product = product_service.get_product_by_sku(sku)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    try:
        image_url = image_service.generate_product_image(
            name=product['name'],
            description=product['description'],
            category=product.get('category', ''),
            sku=sku
        )
        # Update image_url in the database
        product_service.update_product(sku, {
            'name': product['name'],
            'description': product['description'],
            'price': product['price'],
            'currency': product.get('currency', 'EUR'),
            'tags': product.get('tags', ''),
            'stock': product.get('stock', 0),
            'category': product.get('category', ''),
            'image_url': image_url
        })
        return jsonify({'success': True, 'image_url': image_url})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/deliveries', methods=['POST'])
@login_required
def api_create_delivery():
    """API: Create delivery from order."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'JSON data required'}), 400
    
    required = ['order_id', 'customer_name', 'address', 'city']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing: {field}'}), 400
    
    try:
        delivery_id = delivery_service.create_delivery(data)
        delivery = delivery_service.get_delivery_by_id(delivery_id)
        return jsonify({
            'success': True,
            'delivery_id': delivery_id,
            'tracking_number': delivery.get('tracking_number') if delivery else None
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ask', methods=['POST'])
@login_required
def api_ask():
    """API: Natural language query for PostgreSQL, MongoDB, or Azure SQL."""
    data = request.get_json()
    
    if not data or not data.get('question'):
        return jsonify({'error': 'Question is required'}), 400
    
    database = data.get('database', 'postgres')
    
    try:
        if database == 'mongodb':
            result = mongo_nl_query.ask(data['question'])
        elif database == 'azuresql':
            result = azuresql_nl_query.query(data['question'])
        elif database == 'cosmosdb':
            result = cosmos_nl_query.query(data['question'])
        else:
            result = postgres_nl_query.query(data['question'])
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Inventory Agent Routes
# ============================================================================

@app.route('/inventory')
@login_required
def inventory():
    """Inventory dashboard — show stock summary and past reorders."""
    summary = inventory_agent.get_all_stock_summary()
    reorders = inventory_agent.get_reorders(limit=50)
    pending_count = inventory_agent.count_reorders(status='pending')
    return render_template('inventory/index.html',
                           summary=summary,
                           reorders=reorders,
                           pending_count=pending_count)


@app.route('/inventory/check', methods=['POST'])
@login_required
def inventory_check():
    """Run the inventory agent — check stock and create reorders."""
    result = inventory_agent.run()
    count = result.get('reorders_count', 0)
    if count > 0:
        flash(f'Inventory check complete — {count} reorder(s) created.', 'success')
    else:
        flash('Inventory check complete — all products above threshold.', 'info')
    return redirect(url_for('inventory'))


@app.route('/inventory/reorder/<reorder_id>/fulfill', methods=['POST'])
@login_required
def fulfill_reorder(reorder_id):
    """Mark a reorder as received and add stock back to Azure SQL."""
    try:
        result = inventory_agent.fulfill_reorder(reorder_id)
        flash(f'Reorder {reorder_id} fulfilled — +{result["quantity_added"]} units added to {result["sku"]} stock.', 'success')
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        flash(f'Error fulfilling reorder: {e}', 'error')
    return redirect(url_for('inventory'))


@app.route('/inventory/reorder/<reorder_id>/cancel', methods=['POST'])
@login_required
def cancel_reorder(reorder_id):
    """Cancel a pending reorder and delete it from MongoDB."""
    try:
        result = inventory_agent.cancel_reorder(reorder_id)
        flash(f'Reorder {reorder_id} for {result["sku"]} has been cancelled and deleted.', 'success')
    except ValueError as e:
        flash(str(e), 'warning')
    except Exception as e:
        flash(f'Error cancelling reorder: {e}', 'error')
    return redirect(url_for('inventory'))


@app.route('/api/inventory/check', methods=['POST'])
@login_required
def api_inventory_check():
    """API endpoint to run inventory agent (returns JSON)."""
    result = inventory_agent.run()
    return jsonify(result)


@app.route('/api/inventory/reorders')
@login_required
def api_inventory_reorders():
    """API endpoint to list reorders."""
    status = request.args.get('status')
    limit = int(request.args.get('limit', 100))
    reorders = inventory_agent.get_reorders(status=status, limit=limit)
    return jsonify(reorders)


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('UNIFIED_APP_PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
