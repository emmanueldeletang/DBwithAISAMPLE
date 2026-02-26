from flask import Flask

def create_app():
    app = Flask(__name__)
    
    # Load configuration
    app.config.from_object('apps.azure-sql-app.config.Config')

    # Register blueprints
    from apps.azure_sql_app.routes.api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    return app