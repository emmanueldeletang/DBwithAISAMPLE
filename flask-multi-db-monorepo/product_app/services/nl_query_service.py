"""
Natural Language to SQL Service for Azure SQL Products Database
Uses Azure OpenAI to convert natural language queries to SQL and execute them.
"""
import os
import sys
import json
from datetime import datetime
from decimal import Decimal
from openai import AzureOpenAI
from dotenv import load_dotenv

# Add parent path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

try:
    from mssql_python import connect
except ImportError:
    print("mssql-python not installed. Install with: pip install mssql-python")

from shared.config import azure_sql_config

load_dotenv()


# Database schema for context
DATABASE_SCHEMA = """
Database: emedelsql (Azure SQL)

Tables:

1. products
   - sku (VARCHAR 50, PRIMARY KEY) - Unique product identifier (e.g., "ELEC-LAPTOP-001")
   - name (NVARCHAR 200) - Product name
   - description (NVARCHAR MAX) - Detailed product description
   - price (DECIMAL 10,2) - Product price
   - currency (VARCHAR 3, default 'EUR') - Currency code
   - stock (INT) - Available stock quantity
   - category (NVARCHAR 100) - Product category (e.g., "Electronics", "Accessories", "Gaming")
   - tags (NVARCHAR MAX) - JSON array of tags
   - embedding (VECTOR 1536) - Vector embedding for semantic search (do not query this column)
   - created_at (DATETIME2) - Creation timestamp
   - updated_at (DATETIME2) - Last update timestamp

Common Categories:
- Electronics (laptops, tablets, cameras)
- Accessories (cables, chargers, cases)
- Audio (headphones, speakers, microphones)
- Gaming (consoles, controllers, games)
- Storage (SSDs, HDDs, USB drives)
- Computers (desktops, monitors, keyboards)
- Networking (routers, switches, cables)
"""

SYSTEM_PROMPT = """Tu es un assistant expert en SQL pour une base de données Azure SQL de catalogue de produits.

Schéma de la base de données:
{schema}

Règles IMPORTANTES pour Azure SQL (T-SQL):
1. Génère UNIQUEMENT des requêtes SELECT (lecture seule)
2. Utilise TOP au lieu de LIMIT (syntaxe T-SQL): SELECT TOP 10 * FROM products
3. Utilise LIKE pour les recherches de texte (pas ILIKE)
4. Ne sélectionne JAMAIS la colonne 'embedding' (c'est un vecteur binaire)
5. Formate les montants avec 2 décimales
6. Ordonne les résultats de manière logique
7. Pour les comparaisons texte insensibles à la casse, les collations Azure SQL sont généralement CI (Case Insensitive)

Exemples de requêtes valides:
- SELECT TOP 10 sku, name, price, category FROM products ORDER BY price DESC
- SELECT category, COUNT(*) as count, AVG(price) as avg_price FROM products GROUP BY category
- SELECT TOP 5 sku, name, stock FROM products WHERE stock < 10 ORDER BY stock

Réponds UNIQUEMENT avec un objet JSON:
{{
    "sql": "La requête SQL T-SQL",
    "explanation": "Explication en français de ce que fait la requête",
    "columns": ["liste", "des", "colonnes", "retournées"]
}}

Si la question n'est pas liée aux données ou si tu ne peux pas générer une requête SQL valide, réponds:
{{
    "error": "Explication du problème",
    "sql": null
}}
"""


class NLQueryService:
    """Service for natural language to SQL conversion and execution for Azure SQL."""
    
    def __init__(self):
        """Initialize the service with Azure OpenAI client."""
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version="2024-06-01"
        )
        self.deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o')
        self.config = azure_sql_config
    
    def _get_db_connection(self):
        """Create Azure SQL connection using SQL authentication."""
        return self.config.get_connection()
    
    def _serialize_value(self, value):
        """Serialize database value to JSON-compatible format."""
        if value is None:
            return None
        elif isinstance(value, datetime):
            return value.isoformat()
        elif isinstance(value, Decimal):
            return float(value)
        elif isinstance(value, bytes):
            return "[binary data]"
        elif hasattr(value, '__str__'):
            return str(value)
        return value
    
    def generate_sql(self, natural_language_query: str) -> dict:
        """
        Convert a natural language query to SQL.
        
        Args:
            natural_language_query: The user's question in natural language
            
        Returns:
            dict with 'sql', 'explanation', 'columns' or 'error'
        """
        try:
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT.format(schema=DATABASE_SCHEMA)
                    },
                    {
                        "role": "user",
                        "content": natural_language_query
                    }
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            return {
                "error": f"Erreur lors de la génération SQL: {str(e)}",
                "sql": None
            }
    
    def execute_sql(self, sql: str) -> dict:
        """
        Execute a SQL query safely.
        
        Args:
            sql: The SQL query to execute
            
        Returns:
            dict with 'success', 'rows', 'row_count' or 'error'
        """
        # Safety check: only SELECT queries
        sql_upper = sql.strip().upper()
        if not sql_upper.startswith('SELECT'):
            return {
                "success": False,
                "error": "Seules les requêtes SELECT sont autorisées"
            }
        
        # Check for dangerous keywords
        dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE', 'EXEC', 'EXECUTE']
        for keyword in dangerous:
            if keyword in sql_upper:
                return {
                    "success": False,
                    "error": f"Mot-clé interdit détecté: {keyword}"
                }
        
        # Don't select embedding column
        if 'EMBEDDING' in sql_upper and 'SELECT *' not in sql_upper:
            # If explicitly selecting embedding, warn
            pass
        
        try:
            with self._get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                
                # Get column names
                columns = [col[0] for col in cursor.description]
                rows_raw = cursor.fetchall()
                
                # Convert to serializable format
                results = []
                for row in rows_raw:
                    row_dict = {}
                    for i, col in enumerate(columns):
                        # Skip embedding column
                        if col.lower() == 'embedding':
                            continue
                        row_dict[col] = self._serialize_value(row[i])
                    results.append(row_dict)
                
                return {
                    "success": True,
                    "rows": results,
                    "row_count": len(results)
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Erreur d'exécution SQL: {str(e)}"
            }
    
    def query(self, natural_language_query: str) -> dict:
        """
        Complete flow: convert natural language to SQL and execute.
        
        Args:
            natural_language_query: The user's question
            
        Returns:
            Complete result with SQL, explanation, and data
        """
        # Step 1: Generate SQL
        generation_result = self.generate_sql(natural_language_query)
        
        if generation_result.get('error') or not generation_result.get('sql'):
            return {
                "success": False,
                "query": natural_language_query,
                "error": generation_result.get('error', 'Impossible de générer une requête SQL'),
                "sql": None,
                "explanation": None,
                "results": None
            }
        
        sql = generation_result['sql']
        explanation = generation_result.get('explanation', '')
        columns = generation_result.get('columns', [])
        
        # Step 2: Execute SQL
        execution_result = self.execute_sql(sql)
        
        if not execution_result['success']:
            return {
                "success": False,
                "query": natural_language_query,
                "sql": sql,
                "explanation": explanation,
                "error": execution_result['error'],
                "results": None
            }
        
        return {
            "success": True,
            "query": natural_language_query,
            "sql": sql,
            "explanation": explanation,
            "columns": columns,
            "results": execution_result['rows'],
            "row_count": execution_result['row_count']
        }
    
    def get_suggested_questions(self) -> list:
        """Return example natural language queries for the UI."""
        return [
            "Combien de produits avons-nous en catalogue ?",
            "Quels sont les 10 produits les plus chers ?",
            "Liste les produits de la catégorie Electronics",
            "Quels produits ont un stock faible (moins de 10) ?",
            "Quel est le prix moyen par catégorie ?",
            "Quelles sont les différentes catégories de produits ?",
            "Montre les produits ajoutés récemment",
            "Quels produits contiennent 'wireless' dans le nom ?",
            "Combien de produits par catégorie ?",
            "Quels sont les produits en rupture de stock ?"
        ]
