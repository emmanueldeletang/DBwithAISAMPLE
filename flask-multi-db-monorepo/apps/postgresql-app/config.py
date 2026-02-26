DATABASE_URI = "postgresql://username:password@hostname:port/database_name"

class Config:
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = DATABASE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = "your_secret_key"