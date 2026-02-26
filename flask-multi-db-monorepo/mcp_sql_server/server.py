"""
MCP (Model Context Protocol) Server for Azure SQL
Provides tools for querying the Products database via natural language.
"""
import os
import sys
import json
import asyncio
from typing import Any, Optional
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

# mssql-python driver for Azure SQL
try:
    from mssql_python import connect
except ImportError:
    print("mssql-python not installed. Install with: pip install mssql-python", file=sys.stderr)
    sys.exit(1)

load_dotenv()

# ============================================================================
# Database Configuration
# ============================================================================

def get_db_connection():
    """
    Create Azure SQL connection using SQL authentication.
    """
    server = os.getenv('AZURE_SQL_SERVER', '')
    database = os.getenv('AZURE_SQL_DATABASE', 'emedelsql')
    user = os.getenv('AZURE_SQL_USER', '')
    password = os.getenv('AZURE_SQL_PASSWORD', '')
    
    connection_string = (
        f"Server={server};Database={database};"
        f"UID={user};PWD={password};"
        f"Encrypt=yes;TrustServerCertificate=no;"
    )
    
    return connect(connection_string)


# ============================================================================
# Database Schema Information
# ============================================================================

DATABASE_SCHEMA = """
## Database: emedelsql (Azure SQL)

### Tables:

**products**
- sku (VARCHAR 50, PRIMARY KEY) - Unique product identifier
- name (NVARCHAR 200) - Product name
- description (NVARCHAR MAX) - Product description
- price (DECIMAL 10,2) - Product price
- currency (VARCHAR 3, default 'EUR') - Currency code
- stock (INT) - Available stock quantity
- category (NVARCHAR 100) - Product category
- tags (NVARCHAR MAX) - JSON array of tags
- embedding (VECTOR 1536) - Vector embedding for semantic search
- created_at (DATETIME2) - Creation timestamp
- updated_at (DATETIME2) - Last update timestamp

### Categories (examples):
- Electronics
- Accessories  
- Audio
- Gaming
- Storage
- Computers
- Networking

### Common Queries:
- Products by category
- Products in price range
- Low stock products (stock < 10)
- Recently added products
- Search by name or description
"""


# ============================================================================
# MCP Server Setup
# ============================================================================

server = Server("azuresql-products-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools for Azure SQL product queries."""
    return [
        Tool(
            name="get_database_schema",
            description="Get the schema of the Azure SQL products database including table structures and columns.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="execute_query",
            description="Execute a SELECT query on the products database. Only SELECT queries are allowed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute. Must be a valid SELECT statement."
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of rows to return (default 100)",
                        "default": 100
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_table_sample",
            description="Get sample rows from the products table to understand the data structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of sample rows to return (default 5)",
                        "default": 5
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_statistics",
            description="Get statistics about products: counts by category, price ranges, stock levels, etc.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="search_products",
            description="Search products by name, description, SKU, or category.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Term to search for in product name, description, SKU, or category"
                    },
                    "category": {
                        "type": "string",
                        "description": "Optional: Filter by specific category"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="get_low_stock_products",
            description="Get products with low stock (stock quantity below threshold).",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "integer",
                        "description": "Stock threshold (default 10 units)",
                        "default": 10
                    }
                },
                "required": []
            }
        )
    ]


def serialize_value(value: Any) -> Any:
    """Serialize database values to JSON-compatible format."""
    if value is None:
        return None
    elif isinstance(value, datetime):
        return value.isoformat()
    elif isinstance(value, Decimal):
        return float(value)
    elif isinstance(value, bytes):
        return value.hex()
    elif hasattr(value, '__str__'):
        return str(value)
    return value


def row_to_dict(row, columns) -> dict:
    """Convert a database row to dictionary."""
    result = {}
    for i, col in enumerate(columns):
        result[col] = serialize_value(row[i])
    return result


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "get_database_schema":
        return [TextContent(
            type="text",
            text=DATABASE_SCHEMA
        )]
    
    elif name == "execute_query":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 100)
        
        # Safety check: only allow SELECT queries
        clean_query = query.strip().upper()
        if not clean_query.startswith("SELECT"):
            return [TextContent(
                type="text",
                text="Error: Only SELECT queries are allowed for safety reasons."
            )]
        
        # Block dangerous operations
        dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "EXEC", "EXECUTE", "CREATE"]
        for keyword in dangerous_keywords:
            if keyword in clean_query:
                return [TextContent(
                    type="text",
                    text=f"Error: Query contains forbidden keyword: {keyword}"
                )]
        
        # Add TOP if not present (SQL Server syntax)
        if "TOP" not in clean_query and "OFFSET" not in clean_query:
            # Insert TOP after SELECT
            query = query.strip()
            select_pos = query.upper().find("SELECT")
            if select_pos != -1:
                query = query[:select_pos + 6] + f" TOP {limit}" + query[select_pos + 6:]
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                rows = [row_to_dict(row, columns) for row in cursor.fetchall()]
                
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
        limit = arguments.get("limit", 5)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Get sample data (exclude embedding column for readability)
                cursor.execute(f"""
                    SELECT TOP {limit} sku, name, description, price, currency, stock, category, tags, created_at
                    FROM products
                    ORDER BY created_at DESC
                """)
                columns = [col[0] for col in cursor.description]
                rows = [row_to_dict(row, columns) for row in cursor.fetchall()]
                
                # Get column info
                cursor.execute("""
                    SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, CHARACTER_MAXIMUM_LENGTH
                    FROM INFORMATION_SCHEMA.COLUMNS 
                    WHERE TABLE_NAME = 'products'
                    ORDER BY ORDINAL_POSITION
                """)
                col_names = [col[0] for col in cursor.description]
                columns_info = [row_to_dict(row, col_names) for row in cursor.fetchall()]
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "table": "products",
                        "columns": columns_info,
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
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                stats = {}
                
                # Total products
                cursor.execute("SELECT COUNT(*) FROM products")
                stats["total_products"] = cursor.fetchone()[0]
                
                # Products by category
                cursor.execute("""
                    SELECT category, COUNT(*) as count 
                    FROM products 
                    WHERE category IS NOT NULL AND category <> ''
                    GROUP BY category 
                    ORDER BY count DESC
                """)
                columns = ["category", "count"]
                stats["products_by_category"] = [row_to_dict(row, columns) for row in cursor.fetchall()]
                
                # Price statistics
                cursor.execute("""
                    SELECT 
                        MIN(price) as min_price,
                        MAX(price) as max_price,
                        AVG(price) as avg_price
                    FROM products
                """)
                row = cursor.fetchone()
                stats["price_stats"] = {
                    "min_price": float(row[0]) if row[0] else 0,
                    "max_price": float(row[1]) if row[1] else 0,
                    "avg_price": round(float(row[2]), 2) if row[2] else 0
                }
                
                # Stock statistics
                cursor.execute("""
                    SELECT 
                        SUM(stock) as total_stock,
                        AVG(stock) as avg_stock,
                        COUNT(CASE WHEN stock < 10 THEN 1 END) as low_stock_count,
                        COUNT(CASE WHEN stock = 0 THEN 1 END) as out_of_stock_count
                    FROM products
                """)
                row = cursor.fetchone()
                stats["stock_stats"] = {
                    "total_stock": int(row[0]) if row[0] else 0,
                    "avg_stock": round(float(row[1]), 0) if row[1] else 0,
                    "low_stock_products": int(row[2]) if row[2] else 0,
                    "out_of_stock_products": int(row[3]) if row[3] else 0
                }
                
                # Unique categories count
                cursor.execute("SELECT COUNT(DISTINCT category) FROM products WHERE category IS NOT NULL")
                stats["unique_categories"] = cursor.fetchone()[0]
                
                return [TextContent(
                    type="text",
                    text=json.dumps(stats, indent=2, default=str)
                )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    elif name == "search_products":
        search_term = arguments.get("search_term", "")
        category = arguments.get("category", "")
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT TOP 20 sku, name, description, price, currency, stock, category
                    FROM products
                    WHERE (
                        name LIKE ? OR
                        description LIKE ? OR
                        sku LIKE ? OR
                        category LIKE ?
                    )
                """
                params = [f"%{search_term}%"] * 4
                
                if category:
                    query += " AND category = ?"
                    params.append(category)
                
                query += " ORDER BY name"
                
                cursor.execute(query, params)
                columns = [col[0] for col in cursor.description]
                rows = [row_to_dict(row, columns) for row in cursor.fetchall()]
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "search_term": search_term,
                        "category_filter": category or "all",
                        "count": len(rows),
                        "products": rows
                    }, indent=2, default=str)
                )]
        except Exception as e:
            return [TextContent(
                type="text",
                text=f"Error: {str(e)}"
            )]
    
    elif name == "get_low_stock_products":
        threshold = arguments.get("threshold", 10)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                cursor.execute("""
                    SELECT sku, name, category, stock, price
                    FROM products
                    WHERE stock < ?
                    ORDER BY stock ASC
                """, (threshold,))
                
                columns = [col[0] for col in cursor.description]
                rows = [row_to_dict(row, columns) for row in cursor.fetchall()]
                
                return [TextContent(
                    type="text",
                    text=json.dumps({
                        "threshold": threshold,
                        "count": len(rows),
                        "low_stock_products": rows
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
