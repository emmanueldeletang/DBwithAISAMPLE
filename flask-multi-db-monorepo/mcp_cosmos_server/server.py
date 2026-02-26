"""
MCP (Model Context Protocol) Server for Azure Cosmos DB NoSQL
Provides tools for querying the Activity Tracking database via natural language
and generating statistics on user activity.
"""
import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Any
from dotenv import load_dotenv

# Azure Cosmos DB imports
try:
    from azure.cosmos import CosmosClient, PartitionKey, exceptions
except ImportError:
    print("azure-cosmos not installed. Install with: pip install azure-cosmos", file=sys.stderr)
    sys.exit(1)

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

load_dotenv()


# ============================================================================
# Database Configuration
# ============================================================================

def get_container():
    """Create Cosmos DB NoSQL connection and return the container client."""
    endpoint = os.getenv('COSMOS_NOSQL_ENDPOINT', '')
    key = os.getenv('COSMOS_NOSQL_KEY', '')
    database_name = os.getenv('COSMOS_NOSQL_DATABASE', 'useractivities')
    container_name = os.getenv('COSMOS_NOSQL_CONTAINER', 'daily_activities')

    client = CosmosClient(endpoint, credential=key)
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)
    return container


# ============================================================================
# Database Schema Information
# ============================================================================

DATABASE_SCHEMA = """
## Database: useractivities (Azure Cosmos DB NoSQL)

### Container: daily_activities
Partition key: /email

Each document represents one day of activity for a single user.

**Document structure:**
- id (string) - "{email}_{YYYY-MM-DD}" (unique per user per day)
- email (string) - User email address (partition key)
- date (string) - Date in YYYY-MM-DD format
- activities (array of objects):
  - page (string) - Route / URL visited (e.g. "/products", "/orders")
  - action (string) - Verb: "view", "login", "logout", "create_product", "create_order",
    "update_product", "update_order_status", "delete_product", "dispatch_delivery", "submit"
  - timestamp (string) - ISO 8601 UTC timestamp
  - details (string, optional) - Extra information about the action
- first_activity (string) - ISO 8601 timestamp of first activity that day
- last_activity (string) - ISO 8601 timestamp of most recent activity that day

### Composite Index:
- email ASC, date ASC

### Common Queries (Cosmos SQL):
- All activities for a specific date: SELECT * FROM c WHERE c.date = '2026-02-24'
- Activities for a user on a date: SELECT * FROM c WHERE c.email = 'user@example.com' AND c.date = '2026-02-24'
- Distinct users: SELECT DISTINCT c.email FROM c
- Most active users: SELECT c.email, ARRAY_LENGTH(c.activities) AS action_count FROM c WHERE c.date = '2026-02-24' ORDER BY action_count DESC
- Recent activity for a user: SELECT * FROM c WHERE c.email = 'user@example.com' ORDER BY c.date DESC OFFSET 0 LIMIT 7
"""


# ============================================================================
# MCP Server Setup
# ============================================================================

server = Server("cosmosdb-activities-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for Cosmos DB NoSQL activity queries."""
    return [
        Tool(
            name="get_database_schema",
            description="Get the schema of the Cosmos DB NoSQL activity-tracking database including document structure and fields.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_query",
            description="Execute a Cosmos SQL (SELECT) query against the daily_activities container. Only SELECT queries are allowed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The Cosmos SQL SELECT query to execute."
                    },
                    "parameters": {
                        "type": "array",
                        "description": "Optional parameterized query parameters as [{name, value}].",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "string"}
                            }
                        }
                    },
                    "partition_key": {
                        "type": "string",
                        "description": "Optional: email to scope to a single partition (more efficient)."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of documents to return (default 100)",
                        "default": 100
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_sample_documents",
            description="Get sample documents from the daily_activities container to understand the data structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of sample documents to return (default 5)",
                        "default": 5
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_statistics",
            description="Get statistics about user activities: total documents, unique users, activities per day, most active users.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Optional date (YYYY-MM-DD) to get statistics for a specific day. Omit for overall stats."
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_user_activities",
            description="Get all activity documents for a specific user email, optionally filtered by date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The user email address to look up."
                    },
                    "date": {
                        "type": "string",
                        "description": "Optional: specific date (YYYY-MM-DD) to filter."
                    },
                    "days": {
                        "type": "integer",
                        "description": "Optional: number of recent days to fetch (default 7). Ignored if date is provided.",
                        "default": 7
                    }
                },
                "required": ["email"]
            }
        ),
        Tool(
            name="get_activities_for_day",
            description="Get all user activity documents for a specific date (cross-partition query).",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format."
                    }
                },
                "required": ["date"]
            }
        ),
        Tool(
            name="get_distinct_users",
            description="Get the list of all distinct user emails that have activity records.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        )
    ]


def serialize_value(value: Any) -> Any:
    """Serialize Cosmos DB values to JSON-compatible format."""
    if value is None:
        return None
    elif isinstance(value, datetime):
        return value.isoformat()
    return value


def serialize_doc(doc: dict) -> dict:
    """Clean up Cosmos DB system properties for display."""
    cleaned = {}
    for k, v in doc.items():
        if k.startswith('_') and k not in ('_id',):
            continue  # skip _rid, _self, _etag, _attachments, _ts
        cleaned[k] = serialize_value(v)
    return cleaned


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""

    # ========================================================================
    # get_database_schema
    # ========================================================================
    if name == "get_database_schema":
        return [TextContent(type="text", text=DATABASE_SCHEMA)]

    # ========================================================================
    # execute_query
    # ========================================================================
    elif name == "execute_query":
        query = arguments.get("query", "").strip()
        params = arguments.get("parameters", [])
        partition_key = arguments.get("partition_key")
        limit = arguments.get("limit", 100)

        # Safety: only SELECT
        if not query.upper().startswith("SELECT"):
            return [TextContent(type="text", text=json.dumps({
                "error": "Only SELECT queries are allowed."
            }, indent=2))]

        # Reject dangerous keywords
        dangerous = ['DELETE', 'UPDATE', 'INSERT', 'DROP', 'ALTER', 'TRUNCATE', 'CREATE', 'EXEC']
        for kw in dangerous:
            if kw in query.upper():
                return [TextContent(type="text", text=json.dumps({
                    "error": f"Forbidden keyword detected: {kw}"
                }, indent=2))]

        try:
            container = get_container()
            kwargs = {
                "query": query,
                "enable_cross_partition_query": partition_key is None,
                "max_item_count": limit,
            }
            if params:
                kwargs["parameters"] = params
            if partition_key:
                kwargs["partition_key"] = partition_key

            items = list(container.query_items(**kwargs))[:limit]
            results = [serialize_doc(item) for item in items]

            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "query": query,
                "row_count": len(results),
                "results": results
            }, indent=2, default=str))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Query execution failed: {str(e)}"
            }, indent=2))]

    # ========================================================================
    # get_sample_documents
    # ========================================================================
    elif name == "get_sample_documents":
        limit = arguments.get("limit", 5)
        try:
            container = get_container()
            items = list(container.query_items(
                query=f"SELECT TOP {int(limit)} * FROM c ORDER BY c.date DESC",
                enable_cross_partition_query=True,
            ))
            results = [serialize_doc(item) for item in items]
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "count": len(results),
                "documents": results
            }, indent=2, default=str))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to fetch sample documents: {str(e)}"
            }, indent=2))]

    # ========================================================================
    # get_statistics
    # ========================================================================
    elif name == "get_statistics":
        date_filter = arguments.get("date")
        try:
            container = get_container()
            stats = {}

            if date_filter:
                # Stats for a specific day
                items = list(container.query_items(
                    query="SELECT c.email, ARRAY_LENGTH(c.activities) AS action_count, c.first_activity, c.last_activity FROM c WHERE c.date = @date",
                    parameters=[{"name": "@date", "value": date_filter}],
                    enable_cross_partition_query=True,
                ))
                total_actions = sum(item.get('action_count', 0) for item in items)
                stats = {
                    "date": date_filter,
                    "unique_users": len(items),
                    "total_actions": total_actions,
                    "avg_actions_per_user": round(total_actions / len(items), 1) if items else 0,
                    "users": [serialize_doc(item) for item in items]
                }
            else:
                # Overall stats
                # Total documents
                count_result = list(container.query_items(
                    query="SELECT VALUE COUNT(1) FROM c",
                    enable_cross_partition_query=True,
                ))
                total_docs = count_result[0] if count_result else 0

                # Distinct users
                emails = list(container.query_items(
                    query="SELECT DISTINCT c.email FROM c",
                    enable_cross_partition_query=True,
                ))

                # Distinct dates
                dates = list(container.query_items(
                    query="SELECT DISTINCT c.date FROM c",
                    enable_cross_partition_query=True,
                ))

                stats = {
                    "total_documents": total_docs,
                    "unique_users": len(emails),
                    "days_tracked": len(dates),
                    "users": [e['email'] for e in emails],
                    "dates": sorted([d['date'] for d in dates], reverse=True)[:10]
                }

            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "statistics": stats
            }, indent=2, default=str))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to compute statistics: {str(e)}"
            }, indent=2))]

    # ========================================================================
    # get_user_activities
    # ========================================================================
    elif name == "get_user_activities":
        email = arguments.get("email", "").strip()
        date = arguments.get("date")
        days = arguments.get("days", 7)

        if not email:
            return [TextContent(type="text", text=json.dumps({
                "error": "email is required."
            }, indent=2))]

        try:
            container = get_container()

            if date:
                doc_id = f"{email}_{date}"
                try:
                    item = container.read_item(item=doc_id, partition_key=email)
                    return [TextContent(type="text", text=json.dumps({
                        "success": True,
                        "count": 1,
                        "documents": [serialize_doc(item)]
                    }, indent=2, default=str))]
                except exceptions.CosmosResourceNotFoundError:
                    return [TextContent(type="text", text=json.dumps({
                        "success": True,
                        "count": 0,
                        "documents": [],
                        "message": f"No activity found for {email} on {date}"
                    }, indent=2))]
            else:
                items = list(container.query_items(
                    query="SELECT * FROM c WHERE c.email = @email ORDER BY c.date DESC OFFSET 0 LIMIT @limit",
                    parameters=[
                        {"name": "@email", "value": email},
                        {"name": "@limit", "value": days},
                    ],
                    partition_key=email,
                ))
                return [TextContent(type="text", text=json.dumps({
                    "success": True,
                    "count": len(items),
                    "documents": [serialize_doc(item) for item in items]
                }, indent=2, default=str))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to fetch user activities: {str(e)}"
            }, indent=2))]

    # ========================================================================
    # get_activities_for_day
    # ========================================================================
    elif name == "get_activities_for_day":
        date = arguments.get("date", "")
        if not date:
            return [TextContent(type="text", text=json.dumps({
                "error": "date is required (YYYY-MM-DD)."
            }, indent=2))]

        try:
            container = get_container()
            items = list(container.query_items(
                query="SELECT * FROM c WHERE c.date = @date ORDER BY c.last_activity DESC",
                parameters=[{"name": "@date", "value": date}],
                enable_cross_partition_query=True,
            ))
            results = [serialize_doc(item) for item in items]
            total_actions = sum(len(d.get('activities', [])) for d in items)

            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "date": date,
                "user_count": len(results),
                "total_actions": total_actions,
                "documents": results
            }, indent=2, default=str))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to fetch activities for day: {str(e)}"
            }, indent=2))]

    # ========================================================================
    # get_distinct_users
    # ========================================================================
    elif name == "get_distinct_users":
        try:
            container = get_container()
            items = list(container.query_items(
                query="SELECT DISTINCT c.email FROM c",
                enable_cross_partition_query=True,
            ))
            emails = [item['email'] for item in items]
            return [TextContent(type="text", text=json.dumps({
                "success": True,
                "count": len(emails),
                "emails": sorted(emails)
            }, indent=2))]

        except Exception as e:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Failed to fetch distinct users: {str(e)}"
            }, indent=2))]

    # ========================================================================
    # Unknown tool
    # ========================================================================
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
