DATABASE_URI = "mongodb://<username>:<password>@<host>:<port>/<database>?retryWrites=true&w=majority"

class Config:
    DEBUG = True
    MONGO_URI = DATABASE_URI
    SECRET_KEY = "your_secret_key"  # Change this to a random secret key for production
    JSONIFY_PRETTYPRINT_REGULAR = True
    # Add any other configuration settings as needed