from flask import Flask
from shared.database.cosmosdb_mongo import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')

    init_db(app)

    from .routes import api as api_blueprint
    app.register_blueprint(api_blueprint)

    return app