"""
Logistics App - Flask Application (Cosmos DB for MongoDB vCore)
Port: 5003
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-logistics')

from services.partner_service import PartnerService
from services.delivery_service import DeliveryService
from services.search_service import LogisticsSearchService
from services.nl_query_service import NLQueryService

partner_service = PartnerService()
delivery_service = DeliveryService()
search_service = LogisticsSearchService()
nl_query_service = NLQueryService()


# ============================================================================
# DASHBOARD
# ============================================================================

@app.route('/')
def index():
    """Dashboard - overview of logistics."""
    partners_count = partner_service.count_partners()
    deliveries_count = delivery_service.count_deliveries()
    pending_deliveries = delivery_service.count_by_status('pending')
    in_transit = delivery_service.count_by_status('in_transit')
    recent_deliveries = delivery_service.get_recent_deliveries(limit=5)
    
    return render_template('index.html',
                         partners_count=partners_count,
                         deliveries_count=deliveries_count,
                         pending_deliveries=pending_deliveries,
                         in_transit=in_transit,
                         recent_deliveries=recent_deliveries)


# ============================================================================
# PARTNER ROUTES
# ============================================================================

@app.route('/partners')
def partners():
    """List all delivery partners."""
    partners_list = partner_service.get_all_partners()
    return render_template('partners/list.html', partners=partners_list)


@app.route('/partners/<partner_id>')
def partner_detail(partner_id):
    """Partner detail page."""
    partner = partner_service.get_partner_by_id(partner_id)
    if not partner:
        flash('Partner not found', 'error')
        return redirect(url_for('partners'))
    
    deliveries = delivery_service.get_deliveries_by_partner(partner_id)
    
    return render_template('partners/detail.html', partner=partner, deliveries=deliveries)


@app.route('/partners/add', methods=['GET', 'POST'])
def add_partner():
    """Add new partner."""
    if request.method == 'POST':
        data = {
            'name': request.form['name'],
            'contact_email': request.form['contact_email'],
            'contact_phone': request.form.get('contact_phone', ''),
            'service_areas': [x.strip() for x in request.form.get('service_areas', '').split(',') if x.strip()],
            'vehicle_types': [x.strip() for x in request.form.get('vehicle_types', '').split(',') if x.strip()],
            'active': request.form.get('active') == 'on'
        }
        
        try:
            partner_id = partner_service.create_partner(data)
            flash('Partner created successfully!', 'success')
            return redirect(url_for('partner_detail', partner_id=partner_id))
        except Exception as e:
            flash(f'Error creating partner: {str(e)}', 'error')
    
    return render_template('partners/form.html', partner=None, action='Add')


@app.route('/partners/<partner_id>/edit', methods=['GET', 'POST'])
def edit_partner(partner_id):
    """Edit partner."""
    partner = partner_service.get_partner_by_id(partner_id)
    if not partner:
        flash('Partner not found', 'error')
        return redirect(url_for('partners'))
    
    if request.method == 'POST':
        data = {
            'name': request.form['name'],
            'contact_email': request.form['contact_email'],
            'contact_phone': request.form.get('contact_phone', ''),
            'service_areas': [x.strip() for x in request.form.get('service_areas', '').split(',') if x.strip()],
            'vehicle_types': [x.strip() for x in request.form.get('vehicle_types', '').split(',') if x.strip()],
            'active': request.form.get('active') == 'on'
        }
        
        try:
            partner_service.update_partner(partner_id, data)
            flash('Partner updated successfully!', 'success')
            return redirect(url_for('partner_detail', partner_id=partner_id))
        except Exception as e:
            flash(f'Error updating partner: {str(e)}', 'error')
    
    return render_template('partners/form.html', partner=partner, action='Edit')


# ============================================================================
# DELIVERY ROUTES
# ============================================================================

@app.route('/deliveries')
def deliveries():
    """List all deliveries."""
    status_filter = request.args.get('status', '')
    deliveries_list = delivery_service.get_all_deliveries(status=status_filter)
    
    return render_template('deliveries/list.html', 
                         deliveries=deliveries_list,
                         status_filter=status_filter)


@app.route('/deliveries/<delivery_id>')
def delivery_detail(delivery_id):
    """Delivery detail page with tracking history."""
    delivery = delivery_service.get_delivery_by_id(delivery_id)
    if not delivery:
        flash('Delivery not found', 'error')
        return redirect(url_for('deliveries'))
    
    partner = None
    if delivery.get('partner_id'):
        partner = partner_service.get_partner_by_id(delivery['partner_id'])
    
    return render_template('deliveries/detail.html', delivery=delivery, partner=partner)


@app.route('/deliveries/create', methods=['GET', 'POST'])
def create_delivery():
    """Create new delivery."""
    if request.method == 'POST':
        data = {
            'order_id': request.form['order_id'],
            'customer_name': request.form['customer_name'],
            'partner_id': request.form.get('partner_id'),
            'address': request.form['address'],
            'city': request.form['city'],
            'postal_code': request.form.get('postal_code', ''),
            'country': request.form.get('country', 'France'),
            'notes': request.form.get('notes', '')
        }
        
        try:
            delivery_id = delivery_service.create_delivery(data)
            flash('Delivery created successfully!', 'success')
            return redirect(url_for('delivery_detail', delivery_id=delivery_id))
        except Exception as e:
            flash(f'Error creating delivery: {str(e)}', 'error')
    
    partners_list = partner_service.get_all_partners(active_only=True)
    return render_template('deliveries/create.html', partners=partners_list)


@app.route('/deliveries/<delivery_id>/status', methods=['POST'])
def update_delivery_status(delivery_id):
    """Update delivery status with event tracking."""
    new_status = request.form['status']
    status_text = request.form.get('status_text', '')
    location = request.form.get('location', '')
    
    try:
        delivery_service.update_status(delivery_id, new_status, status_text, location)
        flash(f'Delivery status updated to {new_status}', 'success')
    except Exception as e:
        flash(f'Error updating status: {str(e)}', 'error')
    
    return redirect(url_for('delivery_detail', delivery_id=delivery_id))


@app.route('/deliveries/<delivery_id>/assign', methods=['POST'])
def assign_partner(delivery_id):
    """Assign a partner to a delivery."""
    partner_id = request.form['partner_id']
    
    try:
        delivery_service.assign_partner(delivery_id, partner_id)
        flash('Partner assigned successfully!', 'success')
    except Exception as e:
        flash(f'Error assigning partner: {str(e)}', 'error')
    
    return redirect(url_for('delivery_detail', delivery_id=delivery_id))


@app.route('/dispatch')
def dispatch():
    """View pending deliveries awaiting dispatch."""
    pending = delivery_service.get_all_deliveries(status='pending')
    partners = partner_service.get_all_partners(active_only=True)
    
    return render_template('deliveries/dispatch.html', 
                         deliveries=pending,
                         partners=partners)


@app.route('/dispatch/<delivery_id>', methods=['POST'])
def dispatch_delivery(delivery_id):
    """Dispatch a pending delivery to a partner."""
    partner_id = request.form.get('partner_id')
    
    if not partner_id:
        flash('Please select a delivery partner', 'error')
        return redirect(url_for('dispatch'))
    
    try:
        delivery_service.assign_partner(delivery_id, partner_id)
        delivery_service.update_status(delivery_id, 'picked_up', 'Dispatched to delivery partner', 'Warehouse')
        flash('Delivery dispatched successfully!', 'success')
    except Exception as e:
        flash(f'Error dispatching delivery: {str(e)}', 'error')
    
    return redirect(url_for('dispatch'))


# ============================================================================
# NATURAL LANGUAGE QUERIES
# ============================================================================

@app.route('/ask', methods=['GET', 'POST'])
def ask_question():
    """Natural language query interface."""
    result = None
    question = ''
    error = None
    
    if request.method == 'POST':
        question = request.form.get('question', '').strip()
        
        if question:
            try:
                result = nl_query_service.ask(question)
                if not result.get('success', False):
                    error = result.get('error', 'Unknown error')
            except Exception as e:
                error = str(e)
    
    suggested = nl_query_service.get_suggested_questions()
    
    return render_template('ask.html',
                         question=question,
                         result=result,
                         error=error,
                         suggested_questions=suggested)


@app.route('/api/ask', methods=['POST'])
def api_ask():
    """API endpoint for natural language queries."""
    data = request.get_json()
    
    if not data or not data.get('question'):
        return jsonify({'error': 'Question is required'}), 400
    
    question = data['question'].strip()
    
    try:
        result = nl_query_service.ask(question)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# SEARCH
# ============================================================================

@app.route('/search')
def search():
    """Search deliveries with vector and hybrid search."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')
    
    results = []
    search_info = {}
    
    if query:
        if search_type == 'keyword':
            results = search_service.keyword_search(query)
            search_info['method'] = 'Full-Text Search ($text)'
        elif search_type == 'vector':
            results = search_service.vector_search(query)
            search_info['method'] = 'Vector Search (cosmosSearch)'
        else:
            results = search_service.hybrid_search(query)
            search_info['method'] = 'Hybrid Search (RRF)'
        
        search_info['count'] = len(results)
        search_info['query'] = query
    
    return render_template('search.html',
                         results=results,
                         query=query,
                         search_type=search_type,
                         search_info=search_info)


# ============================================================================
# TRACKING (Public)
# ============================================================================

@app.route('/track')
def track():
    """Public tracking page."""
    tracking_number = request.args.get('tracking', '')
    delivery = None
    
    if tracking_number:
        delivery = delivery_service.get_by_tracking_number(tracking_number)
        if not delivery:
            flash('Tracking number not found', 'error')
    
    return render_template('track.html', delivery=delivery, tracking_number=tracking_number)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route('/api/partners')
def api_partners():
    """API: Get all partners."""
    partners_list = partner_service.get_all_partners()
    return jsonify(partners_list)


@app.route('/api/deliveries')
def api_deliveries():
    """API: Get all deliveries."""
    status = request.args.get('status', '')
    deliveries_list = delivery_service.get_all_deliveries(status=status)
    return jsonify(deliveries_list)


@app.route('/api/deliveries/<delivery_id>')
def api_delivery(delivery_id):
    """API: Get delivery details."""
    delivery = delivery_service.get_delivery_by_id(delivery_id)
    if not delivery:
        return jsonify({'error': 'Delivery not found'}), 404
    return jsonify(delivery)


@app.route('/api/deliveries', methods=['POST'])
def api_create_delivery():
    """API: Create a new delivery from an order."""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'JSON data required'}), 400
    
    required_fields = ['order_id', 'customer_name', 'address', 'city']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    try:
        delivery_id = delivery_service.create_delivery(data)
        delivery = delivery_service.get_delivery_by_id(delivery_id)
        return jsonify({
            'success': True,
            'delivery_id': delivery_id,
            'tracking_number': delivery.get('tracking_number') if delivery else None,
            'message': 'Delivery created, awaiting dispatch'
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/deliveries/by-order/<order_id>')
def api_delivery_by_order(order_id):
    """API: Get delivery by order ID."""
    delivery = delivery_service.get_by_order_id(order_id)
    if not delivery:
        return jsonify({'error': 'Delivery not found for this order'}), 404
    return jsonify(delivery)


@app.route('/api/deliveries/<delivery_id>/dispatch', methods=['POST'])
def api_dispatch_delivery(delivery_id):
    """API: Dispatch a delivery to a partner."""
    data = request.get_json()
    
    if not data or not data.get('partner_id'):
        return jsonify({'error': 'partner_id is required'}), 400
    
    try:
        delivery_service.assign_partner(delivery_id, data['partner_id'])
        delivery_service.update_status(delivery_id, 'picked_up', 'Dispatched to delivery partner', 'Warehouse')
        return jsonify({'success': True, 'message': 'Delivery dispatched'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/deliveries/pending')
def api_pending_deliveries():
    """API: Get all pending deliveries awaiting dispatch."""
    deliveries = delivery_service.get_all_deliveries(status='pending')
    return jsonify({'count': len(deliveries), 'deliveries': deliveries})


@app.route('/api/search')
def api_search():
    """API: Search deliveries."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    if search_type == 'keyword':
        results = search_service.keyword_search(query)
    elif search_type == 'vector':
        results = search_service.vector_search(query)
    else:
        results = search_service.hybrid_search(query)
    
    return jsonify({'query': query, 'type': search_type, 'results': results})


@app.route('/api/track/<tracking_number>')
def api_track(tracking_number):
    """API: Track delivery by tracking number."""
    delivery = delivery_service.get_by_tracking_number(tracking_number)
    if not delivery:
        return jsonify({'error': 'Tracking number not found'}), 404
    return jsonify(delivery)


if __name__ == '__main__':
    port = int(os.getenv('LOGISTICS_APP_PORT', 5003))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
