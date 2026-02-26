from flask import jsonify, request
from shared.database.cosmosdb_mongo import get_cosmosdb_client
from shared.search.base_search import BaseSearch

class DocumentSearch(BaseSearch):
    def __init__(self):
        self.client = get_cosmosdb_client()
        self.collection = self.client['your_database_name']['your_collection_name']

    def search_by_keyword(self, keyword):
        results = self.collection.find({"$text": {"$search": keyword}})
        return list(results)

    def search_by_vector(self, vector):
        # Implement vector search logic here
        pass

    def hybrid_search(self, keyword, vector):
        keyword_results = self.search_by_keyword(keyword)
        vector_results = self.search_by_vector(vector)
        # Combine results from both searches
        combined_results = keyword_results + vector_results
        return combined_results

def search_documents():
    keyword = request.args.get('keyword')
    vector = request.args.get('vector')  # Assume vector is passed as a query parameter
    search_service = DocumentSearch()
    
    if keyword and vector:
        results = search_service.hybrid_search(keyword, vector)
    elif keyword:
        results = search_service.search_by_keyword(keyword)
    elif vector:
        results = search_service.search_by_vector(vector)
    else:
        return jsonify({"error": "No search parameters provided"}), 400

    return jsonify(results), 200