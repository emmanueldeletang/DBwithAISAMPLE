"""
Natural Language Query Service for Azure Cosmos DB NoSQL
Uses Azure OpenAI to convert natural language questions to Cosmos SQL queries
and execute them against the activity-tracking container.
"""
import os
import json
from typing import Dict, Any, List
from datetime import datetime
from openai import AzureOpenAI
from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv

load_dotenv()


# Cosmos DB NoSQL configuration
COSMOS_ENDPOINT = os.getenv("COSMOS_NOSQL_ENDPOINT", "")
COSMOS_KEY = os.getenv("COSMOS_NOSQL_KEY", "")
DATABASE_NAME = os.getenv("COSMOS_NOSQL_DATABASE", "useractivities")
CONTAINER_NAME = os.getenv("COSMOS_NOSQL_CONTAINER", "daily_activities")


DATABASE_SCHEMA = """
Database: useractivities (Azure Cosmos DB NoSQL)
Container: daily_activities
Partition key: /email

Each document represents one day of activity for a single user.

Document fields:
- id (string): "{email}_{YYYY-MM-DD}" — unique per user per day
- email (string): User email address (partition key)
- date (string): Date in YYYY-MM-DD format
- activities (array of objects):
    - page (string): Route visited, e.g. "/products", "/orders", "/deliveries"
    - action (string): One of "view", "login", "logout", "create_product", "create_order",
      "update_product", "update_order_status", "delete_product", "dispatch_delivery", "submit"
    - timestamp (string): ISO 8601 UTC timestamp
    - details (string, optional): Extra information
- first_activity (string): ISO 8601 timestamp
- last_activity (string): ISO 8601 timestamp

Composite index: email ASC, date ASC

Important Cosmos SQL notes:
- Use SELECT ... FROM c (the alias 'c' is conventional for the container)
- Array functions: ARRAY_LENGTH(c.activities), ARRAY_CONTAINS(...)
- Cross-partition queries work on all fields
- Use VALUE for scalar results: SELECT VALUE COUNT(1) FROM c
- Use DISTINCT: SELECT DISTINCT c.email FROM c
- Use TOP for limiting: SELECT TOP 10 ... FROM c
- Use OFFSET ... LIMIT for pagination
- For searching inside the activities array use JOIN:
  SELECT c.email, a.page, a.action, a.timestamp FROM c JOIN a IN c.activities WHERE a.action = 'login'
"""

SYSTEM_PROMPT = """You are an expert in Cosmos DB SQL queries for an activity-tracking database.

{schema}

IMPORTANT RULES:
1. Generate ONLY SELECT queries (read-only).
2. Use Cosmos SQL syntax (not T-SQL, not PostgreSQL).
3. The container alias is always 'c'.
4. To query inside the activities array, use JOIN: FROM c JOIN a IN c.activities
5. Use ARRAY_LENGTH(c.activities) to count activities per document.
6. For total counts, use: SELECT VALUE COUNT(1) FROM c
7. Dates are stored as strings in YYYY-MM-DD format.
8. Timestamps are ISO 8601 strings (e.g. "2026-02-24T14:30:00+00:00").
9. Use parameterized queries when filtering by user-provided values.
10. Limit results to 50 unless told otherwise.
11. CRITICAL: Cosmos DB SQL does NOT allow referencing column aliases in ORDER BY, WHERE, or HAVING. You MUST repeat the full expression.
12. Cosmos DB SQL does NOT support GROUP BY. To aggregate, use subqueries or restructure the query.
13. CRITICAL: ORDER BY in Cosmos DB only supports direct document property paths (e.g. ORDER BY c.date DESC, ORDER BY c.email). It does NOT support expressions or function calls in ORDER BY (e.g. ORDER BY ARRAY_LENGTH(c.activities) is INVALID). If you need to sort by a computed value, omit the ORDER BY clause entirely and let the application sort the results.

Return ONLY valid JSON:
{{
    "sql": "The Cosmos SQL query",
    "parameters": [{{ "name": "@param", "value": "value" }}],
    "cross_partition": true or false,
    "partition_key": "email@example.com or null",
    "explanation": "Brief description of what the query does"
}}

If the question cannot be answered, return:
{{
    "error": "Explanation of the problem",
    "sql": null
}}
"""


class CosmosNLQueryService:
    """Service for natural language queries against Cosmos DB NoSQL."""

    def __init__(self):
        self._client = None
        self._container = None

        # Azure OpenAI client
        self.openai_client = AzureOpenAI(
            api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            api_version=os.getenv('AZURE_OPENAI_API_VERSION', '2024-06-01'),
            azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT')
        )
        self.chat_deployment = os.getenv('AZURE_OPENAI_CHAT_DEPLOYMENT', 'gpt-4o')

    def _get_container(self):
        """Get (or create) the Cosmos container client."""
        if self._container is not None:
            return self._container
        self._client = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)
        db = self._client.get_database_client(DATABASE_NAME)
        self._container = db.get_container_client(CONTAINER_NAME)
        return self._container

    # ------------------------------------------------------------------
    # Generate Cosmos SQL from natural language
    # ------------------------------------------------------------------

    def generate_query(self, question: str) -> Dict[str, Any]:
        """Use Azure OpenAI to convert a natural language question to Cosmos SQL."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        # Inject today's date so the AI never uses @today placeholder
        system_content = SYSTEM_PROMPT.format(schema=DATABASE_SCHEMA)
        system_content += f"\n\nIMPORTANT: Today's date is {today}. Use this exact value whenever the user says 'today', 'aujourd'hui', 'today's date', etc. Do NOT use @today as a parameter value — always use the literal date string '{today}'."
        try:
            response = self.openai_client.chat.completions.create(
                model=self.chat_deployment,
                messages=[
                    {"role": "system", "content": system_content},
                    {"role": "user", "content": question}
                ],
                temperature=0.1,
                max_tokens=1000,
                response_format={"type": "json_object"}
            )

            result_text = response.choices[0].message.content.strip()
            # Clean markdown fences if present
            if result_text.startswith("```"):
                lines = result_text.split("\n")
                result_text = "\n".join(lines[1:-1])

            return json.loads(result_text)
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse AI response: {str(e)}", "sql": None}
        except Exception as e:
            return {"error": f"Failed to generate query: {str(e)}", "sql": None}

    # ------------------------------------------------------------------
    # Execute Cosmos SQL safely
    # ------------------------------------------------------------------

    def execute_query(self, query_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a Cosmos SQL query specification."""
        if "error" in query_spec:
            return {"success": False, "error": query_spec["error"]}

        sql = (query_spec.get("sql") or "").strip()
        if not sql:
            return {"success": False, "error": "No SQL query generated."}

        # Safety check
        sql_upper = sql.upper()
        if not sql_upper.startswith("SELECT"):
            return {"success": False, "error": "Only SELECT queries are allowed."}

        dangerous = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER', 'TRUNCATE', 'CREATE', 'EXEC']
        for kw in dangerous:
            if kw in sql_upper:
                return {"success": False, "error": f"Forbidden keyword detected: {kw}"}

        params = query_spec.get("parameters") or []
        cross_partition = query_spec.get("cross_partition", True)
        partition_key = query_spec.get("partition_key")

        # Resolve date placeholders like @today, @yesterday
        today = datetime.utcnow().strftime("%Y-%m-%d")
        for p in params:
            val = p.get("value")
            if isinstance(val, str):
                val_lower = val.lower()
                if val_lower in ("@today", "today", "@date_today"):
                    p["value"] = today
        # Also replace literal @today in the SQL text itself
        if "@today" not in [p.get("name") for p in params]:
            sql = sql.replace("@today", f"'{today}'")

        try:
            container = self._get_container()
            kwargs = {
                "query": sql,
                "enable_cross_partition_query": cross_partition if not partition_key else False,
            }
            if params:
                kwargs["parameters"] = params
            if partition_key:
                kwargs["partition_key"] = partition_key

            items = list(container.query_items(**kwargs))

            # Clean system properties and normalize scalars to dicts
            cleaned = [self._clean_doc(item) for item in items]
            results = []
            for item in cleaned:
                if isinstance(item, dict):
                    results.append(item)
                else:
                    # Scalar values (e.g. COUNT) → wrap as dict for the template
                    results.append({"value": item})

            return {
                "success": True,
                "sql": sql,
                "explanation": query_spec.get("explanation", ""),
                "count": len(results),
                "results": results,
            }
        except Exception as e:
            return {"success": False, "error": f"Query execution failed: {str(e)}", "sql": sql}

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def query(self, question: str) -> Dict[str, Any]:
        """Ask a natural language question and get results from Cosmos DB."""
        query_spec = self.generate_query(question)

        if "error" in query_spec and query_spec.get("sql") is None:
            return {
                "success": False,
                "question": question,
                "error": query_spec["error"]
            }

        result = self.execute_query(query_spec)
        result["question"] = question
        result["generated_query"] = query_spec
        return result

    # ------------------------------------------------------------------
    # Suggested questions for the UI
    # ------------------------------------------------------------------

    @staticmethod
    def get_suggested_questions() -> List[str]:
        return [
            "How many users were active today?",
            "Show all activities for today",
            "How many logins happened today?",
            "Show the last 5 days of activity for all users",
            "List all distinct users tracked",
            "What pages are visited most often?",
            "Show all product creation activities",
            "Who logged in today?",
            "How many orders were created today?",
            "Show activity breakdown by action type",
            "Which users visited the deliveries page?",
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clean_doc(doc):
        """Remove Cosmos DB system properties for cleaner output."""
        if isinstance(doc, dict):
            return {k: v for k, v in doc.items() if not k.startswith('_')}
        # Scalar values (e.g. from SELECT VALUE COUNT(1)) are returned as-is
        return doc
