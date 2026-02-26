from flask import Blueprint, request, jsonify
from ..models.document import Document
from ..services.search import search_documents

api = Blueprint('api', __name__)

@api.route('/documents', methods=['GET'])
def list_documents():
    documents = Document.objects.all()
    return jsonify(documents), 200

@api.route('/documents', methods=['POST'])
def create_document():
    data = request.json
    document = Document(**data)
    document.save()
    return jsonify(document), 201

@api.route('/documents/<document_id>', methods=['PUT'])
def update_document(document_id):
    data = request.json
    document = Document.objects.get(id=document_id)
    for key, value in data.items():
        setattr(document, key, value)
    document.save()
    return jsonify(document), 200

@api.route('/documents/search', methods=['GET'])
def search():
    query = request.args.get('query')
    results = search_documents(query)
    return jsonify(results), 200