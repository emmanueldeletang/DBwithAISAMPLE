from flask import Blueprint, request, jsonify
from ..models.product import Product
from ..services.search import search_products

api = Blueprint('api', __name__)

@api.route('/products', methods=['GET'])
def get_products():
    products = Product.query.all()
    return jsonify([product.to_dict() for product in products]), 200

@api.route('/products', methods=['POST'])
def create_product():
    data = request.json
    new_product = Product(**data)
    new_product.save()
    return jsonify(new_product.to_dict()), 201

@api.route('/products/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    data = request.json
    product = Product.query.get_or_404(product_id)
    for key, value in data.items():
        setattr(product, key, value)
    product.save()
    return jsonify(product.to_dict()), 200

@api.route('/products/search', methods=['GET'])
def search_product():
    query = request.args.get('query')
    results = search_products(query)
    return jsonify(results), 200