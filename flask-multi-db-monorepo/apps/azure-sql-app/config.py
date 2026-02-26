"""
Configuration for Azure SQL Flask App using mssql-python driver
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Flask configuration using mssql-python with Azure AD authentication."""
    
    # Azure SQL Server settings
    AZURE_SQL_SERVER = os.getenv('AZURE_SQL_SERVER', 'edesa.database.windows.net')
    AZURE_SQL_DATABASE = os.getenv('AZURE_SQL_DATABASE', 'emedelsql')
    
    # Connection string for mssql-python with ActiveDirectoryInteractive
    SQL_CONNECTION_STRING = os.getenv(
        'SQL_CONNECTION_STRING',
        f"Server={AZURE_SQL_SERVER};Database={AZURE_SQL_DATABASE};"
        f"Encrypt=yes;TrustServerCertificate=no;Authentication=ActiveDirectoryInteractive"
    )
    
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('DEBUG', 'True').lower() == 'true'