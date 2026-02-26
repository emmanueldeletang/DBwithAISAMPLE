from flask import Blueprint

# Initialize the routes blueprint for the Azure SQL application
azure_sql_routes = Blueprint('azure_sql', __name__)

from .api import *  # Import all routes from the api module