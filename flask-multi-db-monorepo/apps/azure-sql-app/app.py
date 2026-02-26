"""
Azure SQL Flask App - using mssql-python driver
with ActiveDirectoryInteractive authentication
"""
from flask import Flask
import os
import sys

# Add parent directories for shared imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.database.azure_sql import get_db
from apps.azure_sql_app.routes.api import api_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['DEBUG'] = True

app.register_blueprint(api_bp)

@app.route('/')
def index():
    return "Welcome to the Azure SQL Flask App (using mssql-python driver)!"

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')