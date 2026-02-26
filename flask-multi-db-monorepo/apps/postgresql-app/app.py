from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from .config import Config

app = Flask(__name__)
app.config.from_object(Config)

db = SQLAlchemy(app)

from .routes import api

app.register_blueprint(api)

if __name__ == "__main__":
    app.run(debug=os.getenv('FLASK_DEBUG', 'false').lower() == 'true')