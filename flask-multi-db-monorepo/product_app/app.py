"""
Product Catalog App - Flask Application (Azure SQL)
Port: 5001
"""
import os
import sys

# Add parent directory to path for shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-product')

# Import services after app creation
from services.product_service import ProductService
from services.search_service import ProductSearchService
from services.image_service import ImageService

product_service = ProductService()
search_service = ProductSearchService()
image_service = ImageService()


@app.route('/')
def index():
    """Home page - product catalog."""
    page = request.args.get('page', 1, type=int)
    per_page = 12
    
    products = product_service.get_all_products(page=page, per_page=per_page)
    total = product_service.count_products()
    total_pages = (total + per_page - 1) // per_page
    
    return render_template('index.html', 
                         products=products, 
                         page=page, 
                         total_pages=total_pages,
                         total=total)


@app.route('/product/<sku>')
def product_detail(sku):
    """Product detail page."""
    product = product_service.get_product_by_sku(sku)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('index'))
    
    # Get similar products
    similar = search_service.find_similar_products(product['description'], limit=4, exclude_sku=sku)
    
    return render_template('product_detail.html', product=product, similar_products=similar)


@app.route('/product/add', methods=['GET', 'POST'])
def add_product():
    """Add new product."""
    if request.method == 'POST':
        data = {
            'sku': request.form['sku'],
            'name': request.form['name'],
            'description': request.form['description'],
            'price': float(request.form['price']),
            'currency': request.form.get('currency', 'EUR'),
            'tags': request.form.get('tags', ''),
            'stock': int(request.form.get('stock', 0)),
            'category': request.form.get('category', '')
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
            flash(f'Product {data["sku"]} created successfully!', 'success')
            return redirect(url_for('product_detail', sku=data['sku']))
        except Exception as e:
            flash(f'Error creating product: {str(e)}', 'error')
    
    return render_template('product_form.html', product=None, action='Add')


@app.route('/product/<sku>/edit', methods=['GET', 'POST'])
def edit_product(sku):
    """Edit product."""
    product = product_service.get_product_by_sku(sku)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        data = {
            'name': request.form['name'],
            'description': request.form['description'],
            'price': float(request.form['price']),
            'currency': request.form.get('currency', 'EUR'),
            'tags': request.form.get('tags', ''),
            'stock': int(request.form.get('stock', 0)),
            'category': request.form.get('category', '')
        }
        
        try:
            # Handle image: upload or AI-generate
            image_option = request.form.get('image_option', 'none')
            
            if image_option == 'upload' and 'image_file' in request.files:
                file = request.files['image_file']
                if file and file.filename:
                    data['image_url'] = image_service.upload_product_image(sku, file)
                    flash('Image uploaded successfully!', 'info')
            elif image_option == 'generate':
                data['image_url'] = image_service.generate_product_image(
                    name=data['name'],
                    description=data['description'],
                    category=data.get('category', ''),
                    sku=sku
                )
                flash('Image generated with DALL-E!', 'info')
            
            product_service.update_product(sku, data)
            flash('Product updated successfully!', 'success')
            return redirect(url_for('product_detail', sku=sku))
        except Exception as e:
            flash(f'Error updating product: {str(e)}', 'error')
    
    return render_template('product_form.html', product=product, action='Edit')


@app.route('/product/<sku>/delete', methods=['POST'])
def delete_product(sku):
    """Delete product."""
    try:
        product_service.delete_product(sku)
        flash('Product deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting product: {str(e)}', 'error')
    
    return redirect(url_for('index'))


@app.route('/search')
def search():
    """Search page with keyword, vector, and hybrid search."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')
    limit = request.args.get('limit', 20, type=int)
    
    results = []
    search_info = {}
    
    if query:
        if search_type == 'keyword':
            results = search_service.keyword_search(query, limit=limit)
            search_info['method'] = 'Full-Text Search (Azure SQL)'
        elif search_type == 'vector':
            results = search_service.vector_search(query, limit=limit)
            search_info['method'] = 'Vector Search (DiskANN)'
        else:  # hybrid
            results = search_service.hybrid_search(query, limit=limit)
            search_info['method'] = 'Hybrid Search (RRF)'
        
        search_info['count'] = len(results)
        search_info['query'] = query
    
    return render_template('search.html', 
                         results=results, 
                         query=query, 
                         search_type=search_type,
                         search_info=search_info)


# API Endpoints
@app.route('/api/products')
def api_products():
    """API: Get all products."""
    products = product_service.get_all_products(page=1, per_page=100)
    return jsonify(products)


@app.route('/api/products/<sku>')
def api_product(sku):
    """API: Get product by SKU."""
    product = product_service.get_product_by_sku(sku)
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    return jsonify(product)


@app.route('/api/search')
def api_search():
    """API: Search products."""
    query = request.args.get('q', '')
    search_type = request.args.get('type', 'hybrid')
    limit = request.args.get('limit', 20, type=int)
    
    if not query:
        return jsonify({'error': 'Query parameter "q" is required'}), 400
    
    if search_type == 'keyword':
        results = search_service.keyword_search(query, limit=limit)
    elif search_type == 'vector':
        results = search_service.vector_search(query, limit=limit)
    else:
        results = search_service.hybrid_search(query, limit=limit)
    
    return jsonify({
        'query': query,
        'type': search_type,
        'count': len(results),
        'results': results
    })


@app.route('/api/products/<sku>/image')
def api_product_image(sku):
    """API: Proxy product image from blob storage."""
    image_bytes = image_service.get_image_proxy(sku)
    if image_bytes:
        return Response(
            image_bytes,
            mimetype='image/png',
            headers={
                'Cache-Control': 'public, max-age=86400',
                'Content-Disposition': f'inline; filename="{sku}.png"'
            }
        )
    return '', 404


@app.route('/api/products/<sku>/generate-image', methods=['POST'])
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


if __name__ == '__main__':
    port = int(os.getenv('PRODUCT_APP_PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')
