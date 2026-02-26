# MongoDB MCP Server

MCP (Model Context Protocol) server for querying the MongoDB Logistics database using natural language.

## Features

- **Natural Language Queries**: Query deliveries and partners using conversational language
- **Predefined Statistics**: Ready-to-use aggregation pipelines for common analytics
- **Custom Aggregations**: Run custom MongoDB aggregation pipelines
- **Dashboard Stats**: Get comprehensive dashboard with key metrics
- **Delivery Tracking**: Track deliveries by tracking number or ID
- **Partner Analytics**: View partner performance and workload

## Tools Available

| Tool | Description |
|------|-------------|
| `get_database_schema` | Get MongoDB schema for deliveries and partners collections |
| `find_documents` | Query documents with filters, projection, sorting |
| `run_aggregation` | Run custom MongoDB aggregation pipelines |
| `list_predefined_stats` | List available predefined statistics |
| `run_predefined_stats` | Run a predefined statistic by name |
| `get_collection_sample` | Get sample documents to understand data structure |
| `get_dashboard_stats` | Get comprehensive dashboard with all key metrics |
| `search_deliveries` | Search deliveries by customer, tracking number, city |
| `track_delivery` | Get detailed tracking info for a delivery |
| `get_partner_details` | Get partner info with delivery statistics |

## Predefined Statistics

- `deliveries_by_status` - Count deliveries by status
- `deliveries_by_city` - Count deliveries by destination city
- `deliveries_by_partner` - Count deliveries by partner
- `pending_deliveries_by_city` - Pending deliveries by city
- `partner_performance` - Partner performance breakdown
- `active_partners_summary` - Active partners with service areas
- `deliveries_timeline` - Deliveries per day (last 30 days)
- `delivery_notes_analysis` - Most common delivery notes

## Installation

```bash
pip install mcp pymongo python-dotenv
```

## Configuration

Add to your `.env` file:

```ini
MONGODB_HOST=your-cluster.mongocluster.cosmos.azure.com
MONGODB_DATABASE=logisticsdb
MONGODB_USER=your-username
MONGODB_PASSWORD=your-password
```

## VS Code MCP Configuration

Add to your VS Code settings or `mcp_config.json`:

```json
{
  "mcpServers": {
    "mongodb-logistics": {
      "command": "python",
      "args": ["mcp_mongo_server/server.py"],
      "cwd": "${workspaceFolder}/flask-multi-db-monorepo",
      "env": {
        "MONGODB_HOST": "${env:MONGODB_HOST}",
        "MONGODB_DATABASE": "${env:MONGODB_DATABASE}",
        "MONGODB_USER": "${env:MONGODB_USER}",
        "MONGODB_PASSWORD": "${env:MONGODB_PASSWORD}"
      }
    }
  }
}
```

## Usage Examples

### Ask in natural language:
- "How many deliveries are pending?"
- "Show me deliveries in Paris"
- "What's the partner performance breakdown?"
- "Track delivery TRK1234567890"
- "List top 5 cities by delivery count"

### Example Queries:

**Find pending deliveries:**
```json
{
  "collection": "deliveries",
  "filter": {"status": "pending"},
  "limit": 10
}
```

**Run custom aggregation:**
```json
{
  "collection": "deliveries",
  "pipeline": [
    {"$match": {"address.city": "Paris"}},
    {"$group": {"_id": "$status", "count": {"$sum": 1}}}
  ]
}
```

## Running the Server

```bash
cd flask-multi-db-monorepo
python mcp_mongo_server/server.py
```

The server communicates via stdio and is designed to be launched by an MCP client (like VS Code with GitHub Copilot).
