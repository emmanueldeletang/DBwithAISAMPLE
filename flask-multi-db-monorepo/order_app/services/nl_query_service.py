"""
Natural Language to SQL Service
Uses Azure OpenAI to convert natural language queries to SQL and execute them.
"""
import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from openai import AzureOpenAI
from dotenv import load_dotenv

load_dotenv()

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.database.postgresql import get_pooled_connection


# Database schema for context
DATABASE_SCHEMA = """
Database: ordersdb (PostgreSQL)

Tables:

1. customers
   - customer_id (UUID, PRIMARY KEY)
   - first_name (VARCHAR 100)
   - last_name (VARCHAR 100) 
   - email (VARCHAR 255, UNIQUE)
   - phone (VARCHAR 50)
   - address (TEXT)
   - city (VARCHAR 100)
   - country (VARCHAR 100)
   - created_at (TIMESTAMP)
   - updated_at (TIMESTAMP)

2. orders
   - order_id (UUID, PRIMARY KEY)
   - customer_id (UUID, FOREIGN KEY -> customers.customer_id)
   - order_date (TIMESTAMP)
   - status (VARCHAR 50) - values: 'pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled'
   - total_amount (DECIMAL 12,2)
   - currency (VARCHAR 3, default 'EUR')
   - notes (TEXT)
   - created_at (TIMESTAMP)
   - updated_at (TIMESTAMP)

3. order_items
   - order_item_id (UUID, PRIMARY KEY)
   - order_id (UUID, FOREIGN KEY -> orders.order_id)
   - product_sku (VARCHAR 50)
   - product_name (VARCHAR 200)
   - quantity (INT)
   - unit_price (DECIMAL 10,2)
   - created_at (TIMESTAMP)

Relationships:
- customers (1) -> orders (many)
- orders (1) -> order_items (many)
"""

SYSTEM_PROMPT = """Tu es un assistant expert en SQL pour une base de données PostgreSQL de gestion de commandes.

Schéma de la base de données:
{schema}

Règles:
1. Génère UNIQUEMENT des requêtes SELECT (lecture seule)
2. Utilise TOUJOURS LIMIT pour éviter les résultats trop volumineux (max 100 lignes)
3. Utilise des alias clairs pour les colonnes
4. Pour les recherches de texte, utilise ILIKE pour être insensible à la casse
5. Formate les montants avec 2 décimales
6. Ordonne les résultats de manière logique
7. Joins les tables si nécessaire pour enrichir les résultats

Réponds UNIQUEMENT avec un objet JSON:
{{
    "sql": "La requête SQL",
    "explanation": "Explication en français de ce que fait la requête",
    "columns": ["liste", "des", "colonnes", "retournées"]
}}

Si la question n'est pas liée aux données ou si tu ne peux pas générer une requête SQL valide, réponds:
{{
    "error": "Explication du problème",
    "sql": null
}}
"""


class NaturalLanguageQueryService:
    """Service for natural language to SQL conversion and execution."""
    
    def __init__(self):
        """Initialize the service with Azure OpenAI client."""
        self.client = AzureOpenAI(
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version="2024-06-01"
        )
        self.deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o')
    
    def _get_db_connection(self):
        """Get a pooled PostgreSQL connection."""
        return get_pooled_connection()
    
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
        dangerous = ['DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'TRUNCATE', 'CREATE']
        for keyword in dangerous:
            if keyword in sql_upper:
                return {
                    "success": False,
                    "error": f"Mot-clé interdit détecté: {keyword}"
                }
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Convert to serializable format
            results = []
            for row in rows:
                row_dict = dict(row)
                for key, value in row_dict.items():
                    if hasattr(value, 'isoformat'):
                        row_dict[key] = value.isoformat()
                    elif hasattr(value, 'hex'):
                        row_dict[key] = str(value)
                    elif isinstance(value, (int, float)):
                        row_dict[key] = float(value) if '.' in str(value) else int(value)
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
    
    def get_example_queries(self) -> list:
        """Return example natural language queries for the UI."""
        return [
            "Combien de clients avons-nous ?",
            "Quels sont les 10 clients avec le plus de commandes ?",
            "Quel est le montant total des ventes par statut de commande ?",
            "Liste les commandes en attente (pending)",
            "Quels sont les clients de Paris ?",
            "Quel est le panier moyen par client ?",
            "Quels produits sont les plus commandés ?",
            "Affiche les dernières 5 commandes avec les détails du client",
            "Combien de commandes ont été livrées ce mois-ci ?",
            "Quels clients n'ont pas encore passé de commande ?"
        ]
