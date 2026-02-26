from flask import Blueprint

# Initialize the routes blueprint for the PostgreSQL application
postgresql_routes = Blueprint('postgresql', __name__)

from .api import *  # Import all routes from the api module