"""
Shared configuration module - reads from environment variables
Supports SQL authentication for Azure SQL
"""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class AzureSQLConfig:
    """
    Azure SQL configuration using SQL authentication (user/password).
    """
    server: str = os.getenv("AZURE_SQL_SERVER", "")
    database: str = os.getenv("AZURE_SQL_DATABASE", "emedelsql")
    port: int = int(os.getenv("AZURE_SQL_PORT", "1433"))
    user: str = os.getenv("AZURE_SQL_USER", "")
    password: str = os.getenv("AZURE_SQL_PASSWORD", "")

    @property
    def connection_string(self) -> str:
        """Connection string for mssql-python driver with SQL authentication."""
        return (
            f"Server={self.server};Database={self.database};"
            f"UID={self.user};PWD={self.password};"
            f"Encrypt=yes;TrustServerCertificate=no;"
        )
    
    def get_connection(self):
        """Get a database connection using mssql-python."""
        from mssql_python import connect
        return connect(self.connection_string)


@dataclass
class PostgresConfig:
    host: str = os.getenv("POSTGRES_HOST", "")
    port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    database: str = os.getenv("POSTGRES_DATABASE", "ordersdb")
    user: str = os.getenv("POSTGRES_USER", "")
    password: str = os.getenv("POSTGRES_PASSWORD", "")
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}?sslmode=require"


@dataclass
class MongoDBConfig:
    host: str = os.getenv("MONGODB_HOST", "")
    user: str = os.getenv("MONGODB_USER", "")
    password: str = os.getenv("MONGODB_PASSWORD", "")
    database: str = os.getenv("MONGODB_DATABASE", "logisticsdb")
    
    @property
    def connection_string(self) -> str:
        return (
            f"mongodb+srv://{self.user}:{self.password}@{self.host}/"
            f"?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
        )


@dataclass
class AzureOpenAIConfig:
    endpoint: str = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    api_key: str = os.getenv("AZURE_OPENAI_API_KEY", "")
    embedding_deployment: str = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")
    # Use 1536 dimensions for Azure SQL compatibility (max 1998)
    embedding_dimension: int = int(os.getenv("AZURE_OPENAI_EMBEDDING_DIMENSION", "1536"))


# Singleton instances
azure_sql_config = AzureSQLConfig()
postgres_config = PostgresConfig()
mongodb_config = MongoDBConfig()
openai_config = AzureOpenAIConfig()
