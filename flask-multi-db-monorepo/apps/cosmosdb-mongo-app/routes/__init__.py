from flask import Blueprint

bp = Blueprint('cosmosdb_mongo', __name__)

from . import api