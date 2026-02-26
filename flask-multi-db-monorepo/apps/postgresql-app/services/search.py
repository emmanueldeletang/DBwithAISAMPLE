from flask import jsonify
from sqlalchemy.orm import Session
from ..models.product import Product

def search_products(session: Session, query: str):
    results = session.query(Product).filter(Product.name.ilike(f'%{query}%')).all()
    return jsonify([product.to_dict() for product in results])

def search_products_by_category(session: Session, category: str):
    results = session.query(Product).filter(Product.category == category).all()
    return jsonify([product.to_dict() for product in results])