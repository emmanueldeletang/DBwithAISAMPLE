# MCP Cosmos DB NoSQL Server

Model Context Protocol (MCP) server for querying the Cosmos DB NoSQL **User Activities** database using natural language.

## Tools

| Tool | Description |
|------|-------------|
| `get_database_schema` | Returns the schema of the `daily_activities` container |
| `execute_query` | Executes a Cosmos SQL query (SELECT only) |
| `get_sample_documents` | Returns sample documents from the container |
| `get_statistics` | Gets activity statistics (overall or for a specific day) |
| `get_user_activities` | Gets activities for a specific user by email |
| `get_activities_for_day` | Gets all activities for a given date |
| `get_distinct_users` | Lists all distinct user emails |

## Running

```bash
python mcp_cosmos_server/server.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `COSMOS_NOSQL_ENDPOINT` | Cosmos DB account endpoint URL |
| `COSMOS_NOSQL_KEY` | Cosmos DB account key |
| `COSMOS_NOSQL_DATABASE` | Database name (default: `useractivities`) |
| `COSMOS_NOSQL_CONTAINER` | Container name (default: `daily_activities`) |
