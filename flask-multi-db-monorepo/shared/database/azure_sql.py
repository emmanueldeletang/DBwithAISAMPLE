"""Azure SQL Database connection using mssql-python driver.

Uses ActiveDirectoryDefault authentication for Azure AD login.
No password required - authenticates using DefaultAzureCredential (az login, etc).
"""
import os
from mssql_python import connect
from dotenv import load_dotenv

load_dotenv()


def get_connection_string(user_email: str = None) -> str:
    """Build the connection string for Azure SQL using mssql-python.
    
    Args:
        user_email: Optional email for Entra ID authentication (UID parameter).
    """
    server = os.getenv('AZURE_SQL_SERVER', 'edesa.database.windows.net')
    database = os.getenv('AZURE_SQL_DATABASE', 'emedelsql')
    
    # Use environment variable if set, otherwise build default
    cs = os.getenv(
        'SQL_CONNECTION_STRING',
        f"Server={server};Database={database};Encrypt=yes;TrustServerCertificate=no;Authentication=ActiveDirectoryDefault"
    )
    
    # Add UID if email provided and not already present
    if user_email and 'UID=' not in cs:
        cs += f";UID={user_email}"
    
    return cs


def get_db():
    """
    Get a database connection using mssql-python.
    
    Usage:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        results = cursor.fetchall()
        conn.close()
    
    Or as context manager:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM products")
            results = cursor.fetchall()
    """
    connection_string = get_connection_string()
    return connect(connection_string)


class AzureSQLConnection:
    """Context manager for Azure SQL connections using mssql-python."""
    
    def __init__(self):
        self._conn = None
    
    def __enter__(self):
        self._conn = get_db()
        return self._conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn:
            self._conn.close()
        return False