"""
MCP (Model Context Protocol) Server for PostgreSQL
Provides tools for querying the Orders database via natural language.
"""
import os
import sys
import json
import asyncio
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Optional
from dotenv import load_dotenv

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

def get_db_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=int(os.getenv('POSTGRES_PORT', 5432)),
        database=os.getenv('POSTGRES_DATABASE', 'ordersdb'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', ''),
        sslmode=os.getenv('POSTGRES_SSL_MODE', 'require'),
        cursor_factory=RealDictCursor
    )


# ============================================================================
# Database Schema Information
# ============================================================================

DATABASE_SCHEMA = """
## Database: ordersdb (PostgreSQL)

### Tables:

**customers**
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

**orders**
- order_id (UUID, PRIMARY KEY)
- customer_id (UUID, FOREIGN KEY -> customers)
- order_date (TIMESTAMP)
- status (VARCHAR 50: 'pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')
- total_amount (DECIMAL 12,2)
- currency (VARCHAR 3, default 'EUR')
- notes (TEXT)
- created_at (TIMESTAMP)
- updated_at (TIMESTAMP)

**order_items**
- order_item_id (UUID, PRIMARY KEY)
- order_id (UUID, FOREIGN KEY -> orders)
- product_sku (VARCHAR 50)
- product_name (VARCHAR 200)
- quantity (INT)
- unit_price (DECIMAL 10,2)
- created_at (TIMESTAMP)

### Common Queries:
- Total orders by status
- Revenue by customer
- Orders by date range
- Top customers by total spend
- Average order value
"""


# ============================================================================
# MCP Server
# ============================================================================

server = Server("postgres-orders-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_database_schema",
            description="Get the database schema information for the Orders database (PostgreSQL). Use this to understand the tables and columns available before writing queries.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_query",
            description="Execute a read-only SQL query against the Orders PostgreSQL database. Only SELECT queries are allowed for safety.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return (default: 100)",
                        "default": 100
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_table_sample",
            description="Get a sample of rows from a specific table to understand the data format.",
            inputSchema={
                "type": "object",
                "properties": {
                    "table_name": {
                        "type": "string",
                        "description": "Name of the table (customers, orders, order_items)",
                        "enum": ["customers", "orders", "order_items"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of sample rows (default: 5)",
                        "default": 5
                    }
                },
                "required": ["table_name"]
            }
        ),
        Tool(
            name="get_statistics",
            description="Get summary statistics for the Orders database including counts, totals, and averages.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="search_customers",
            description="Search for customers by name, email, or city.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "The search term to look for in customer records"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="get_customer_orders",
            description="Get all orders for a specific customer by their email or name.",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_identifier": {
                        "type": "string",
                        "description": "Customer email or name to search for"
                    }
                },
                "required": ["customer_identifier"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "get_database_schema":
        return [TextContent(type="text", text=DATABASE_SCHEMA)]
    
    elif name == "execute_query":
        query = arguments.get("query", "").strip()
        limit = arguments.get("limit", 100)
        
        # Safety check: only allow SELECT queries
        if not query.upper().startswith("SELECT"):
            return [TextContent(
                type="text",
                text="Error: Only SELECT queries are allowed for safety reasons."
            )]
        
        # Add LIMIT if not present
        if "LIMIT" not in query.upper():
            query = f"{query} LIMIT {limit}"
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(query)
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            # Convert to JSON-serializable format
            rows = [dict(row) for row in results]
            # Handle UUID and datetime serialization
            for row in rows:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif hasattr(value, 'hex'):
                        row[key] = str(value)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": True,
                    "row_count": len(rows),
                    "results": rows
                }, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=json.dumps({
                    "success": False,
                    "error": str(e)
                })
            )]
    
    elif name == "get_table_sample":
        table_name = arguments.get("table_name")
        limit = arguments.get("limit", 5)
        
        if table_name not in ["customers", "orders", "order_items"]:
            return [TextContent(
                type="text",
                text="Error: Invalid table name. Use: customers, orders, or order_items"
            )]
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_name} LIMIT %s", (limit,))
            results = cursor.fetchall()
            
            # Get column info
            cursor.execute(f"""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))
            columns = cursor.fetchall()
            
            cursor.close()
            conn.close()
            
            rows = [dict(row) for row in results]
            for row in rows:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif hasattr(value, 'hex'):
                        row[key] = str(value)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "table": table_name,
                    "columns": [dict(c) for c in columns],
                    "sample_rows": rows
                }, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    elif name == "get_statistics":
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Customer stats
            cursor.execute("SELECT COUNT(*) as count FROM customers")
            stats["total_customers"] = cursor.fetchone()["count"]
            
            cursor.execute("SELECT COUNT(DISTINCT city) as count FROM customers")
            stats["unique_cities"] = cursor.fetchone()["count"]
            
            # Order stats
            cursor.execute("SELECT COUNT(*) as count FROM orders")
            stats["total_orders"] = cursor.fetchone()["count"]
            
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM orders 
                GROUP BY status 
                ORDER BY count DESC
            """)
            stats["orders_by_status"] = [dict(r) for r in cursor.fetchall()]
            
            cursor.execute("SELECT SUM(total_amount) as total FROM orders")
            result = cursor.fetchone()
            stats["total_revenue"] = float(result["total"]) if result["total"] else 0
            
            cursor.execute("SELECT AVG(total_amount) as avg FROM orders")
            result = cursor.fetchone()
            stats["average_order_value"] = round(float(result["avg"]), 2) if result["avg"] else 0
            
            # Order items stats
            cursor.execute("SELECT COUNT(*) as count FROM order_items")
            stats["total_order_items"] = cursor.fetchone()["count"]
            
            cursor.close()
            conn.close()
            
            return [TextContent(
                type="text",
                text=json.dumps(stats, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    elif name == "search_customers":
        search_term = arguments.get("search_term", "")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT customer_id, first_name, last_name, email, phone, city, country
                FROM customers
                WHERE 
                    first_name ILIKE %s OR
                    last_name ILIKE %s OR
                    email ILIKE %s OR
                    city ILIKE %s
                LIMIT 20
            """, (f"%{search_term}%",) * 4)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            rows = [dict(row) for row in results]
            for row in rows:
                for key, value in row.items():
                    if hasattr(value, 'hex'):
                        row[key] = str(value)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "search_term": search_term,
                    "count": len(rows),
                    "customers": rows
                }, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    elif name == "get_customer_orders":
        identifier = arguments.get("customer_identifier", "")
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT 
                    c.first_name, c.last_name, c.email,
                    o.order_id, o.order_date, o.status, o.total_amount, o.currency
                FROM customers c
                JOIN orders o ON c.customer_id = o.customer_id
                WHERE 
                    c.email ILIKE %s OR
                    c.first_name ILIKE %s OR
                    c.last_name ILIKE %s OR
                    CONCAT(c.first_name, ' ', c.last_name) ILIKE %s
                ORDER BY o.order_date DESC
                LIMIT 50
            """, (f"%{identifier}%",) * 4)
            
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            rows = [dict(row) for row in results]
            for row in rows:
                for key, value in row.items():
                    if hasattr(value, 'isoformat'):
                        row[key] = value.isoformat()
                    elif hasattr(value, 'hex'):
                        row[key] = str(value)
                    elif isinstance(value, (int, float)) and key == 'total_amount':
                        row[key] = float(value)
            
            return [TextContent(
                type="text",
                text=json.dumps({
                    "search": identifier,
                    "count": len(rows),
                    "orders": rows
                }, indent=2, default=str)
            )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
