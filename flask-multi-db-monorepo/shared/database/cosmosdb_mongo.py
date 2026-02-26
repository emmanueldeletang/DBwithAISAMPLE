from pymongo import MongoClient
import os

class CosmosDBMongo:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None

    def connect(self):
        mongo_uri = os.getenv("COSMOSDB_MONGO_URI")
        self.client = MongoClient(mongo_uri)
        self.db = self.client.get_database(os.getenv("COSMOSDB_DATABASE_NAME"))
        self.collection = self.db.get_collection(os.getenv("COSMOSDB_COLLECTION_NAME"))

    def insert_document(self, document):
        return self.collection.insert_one(document)

    def find_document(self, query):
        return self.collection.find_one(query)

    def search_documents(self, query):
        return list(self.collection.find(query))

    def update_document(self, query, update):
        return self.collection.update_one(query, {"$set": update})

    def delete_document(self, query):
        return self.collection.delete_one(query)