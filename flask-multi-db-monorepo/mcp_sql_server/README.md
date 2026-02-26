# Azure SQL MCP Server

MCP (Model Context Protocol) server for querying the Azure SQL Products database via natural language.

## Features

- **get_database_schema**: Get the schema of the products database
- **execute_query**: Execute SELECT queries on the database
- **get_table_sample**: Get sample data from the products table
- **get_statistics**: Get aggregate statistics (counts, prices, stock levels)
- **search_products**: Search products by name, description, SKU, or category
- **get_low_stock_products**: Find products with stock below a threshold

## Setup

### Prerequisites

1. Python 3.10+
2. MCP SDK: `pip install mcp`
3. mssql-python driver: `pip install mssql-python`
4. Azure CLI logged in: `az login`

### Environment Variables

```bash
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=emedelsql
```

### Running the Server

```bash
cd mcp_sql_server
python server.py
```

## MCP Configuration

Add this server to your MCP client configuration:

```json
{
  "mcpServers": {
    "azuresql-products": {
      "command": "python",
      "args": ["server.py"],
      "cwd": "./mcp_sql_server"
    }
  }
}
```

## Example Queries

- "Show me all electronics products"
- "What products have low stock?"
- "What's the average price by category?"
- "Find products containing 'wireless' in the name"
