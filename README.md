# Flask Multi-Database Demo 🚀

A demonstration project showcasing **multi-database architecture** with a unified Flask application connected to four Azure database services. Features include **vector similarity search**, **natural language queries**, **MCP (Model Context Protocol) servers**, **activity tracking**, and a modern **Bootstrap UI**.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0+-green)
![Azure SQL](https://img.shields.io/badge/Azure_SQL-mssql--python-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-azure__ai+DiskANN-orange)
![MongoDB](https://img.shields.io/badge/Cosmos_DB-MongoDB_vCore-green)
![Cosmos DB NoSQL](https://img.shields.io/badge/Cosmos_DB-NoSQL-orange)

## 🎯 Overview

| Database | Domain | Driver/Extensions | Features |
|----------|--------|-------------------|----------|
| **Azure SQL** | Product Catalog | `mssql-python` + VECTOR(1536) | Vector search, SQL auth |
| **PostgreSQL** | Customers & Orders | `azure_ai` + `pg_diskann` | Auto-embeddings, DiskANN index |
| **MongoDB vCore** | Logistics & Deliveries | `pymongo` + cosmosSearch | Full-text search, vector search |
| **Cosmos DB NoSQL** | Activity Tracking | `azure-cosmos` SDK | Per-user daily log, composite index |

## ✨ Key Features

### 🔐 Authentication
- **Local email/password** authentication with **bcrypt** password hashing
- User accounts stored in **PostgreSQL** (`app_users` table)
- **User management UI** (create, edit, change password, delete)
- Session-based authentication with `flask-session`

### 🔍 Vector Search with Auto-Generated Embeddings
- **Azure SQL**: Native `VECTOR(1536)` type with `VECTOR_DISTANCE('cosine', ...)`
- **PostgreSQL**: `azure_ai.create_embeddings()` with DiskANN/HNSW indexing
- **MongoDB vCore**: `cosmosSearch` aggregation pipeline

### 💬 Natural Language Queries
Ask questions in plain language → AI generates SQL/MongoDB/Cosmos SQL queries:
- "Quels produits ont un stock faible ?" → Azure SQL
- "Combien de commandes ce mois-ci ?" → PostgreSQL
- "Livraisons en retard ?" → MongoDB
- "Qui s'est connecté aujourd'hui ?" → Cosmos DB NoSQL

### 🔌 MCP (Model Context Protocol) Servers
Enable AI agents (GitHub Copilot) to query databases directly:
- `mcp_sql_server/` - Azure SQL products
- `mcp_postgres_server/` - PostgreSQL orders
- `mcp_mongo_server/` - MongoDB logistics
- `mcp_cosmos_server/` - Cosmos DB NoSQL activity tracking

### 📊 Activity Tracking & Audit
- **Cosmos DB NoSQL** stores per-user daily activity documents
- Partition key: `/email`, composite index on email + date
- Activity log UI with date and email filters
- NL query support ("Who logged in today?", "Most active user?")

## 📂 Project Structure
all the code is in the zip code.zip , unzip to get access 
```
flask-multi-db-monorepo/
├── unified_app/              # Main Flask application (Port 5000)
│   ├── app.py               # Routes for all four databases
│   ├── services/
│   │   ├── user_service.py  # User CRUD + bcrypt auth (PostgreSQL)
│   │   ├── activity_tracking_service.py  # Activity tracking (Cosmos DB NoSQL)
│   │   └── cosmos_nl_query_service.py    # NL → Cosmos SQL
│   └── templates/           # Bootstrap UI templates
│
├── product_app/              # Azure SQL services
│   └── services/
│       ├── product_service.py
│       ├── search_service.py
│       └── nl_query_service.py    # Natural language → T-SQL
│
├── order_app/                # PostgreSQL services
│   └── services/
│       ├── customer_service.py
│       ├── order_service.py
│       └── nl_query_service.py    # Natural language → SQL
│
├── logistics_app/            # MongoDB services
│   └── services/
│       ├── partner_service.py
│       ├── delivery_service.py
│       └── nl_query_service.py    # Natural language → MongoDB
│
├── mcp_sql_server/           # MCP Server for Azure SQL
│   └── server.py
├── mcp_postgres_server/      # MCP Server for PostgreSQL
│   └── server.py
├── mcp_mongo_server/         # MCP Server for MongoDB
│   └── server.py
├── mcp_cosmos_server/        # MCP Server for Cosmos DB NoSQL
│   └── server.py
│
├── shared/                   # Shared utilities
│   ├── config.py            # Environment configuration
│   ├── embeddings.py        # Azure OpenAI embeddings
│   └── hybrid_rank.py       # RRF ranking for hybrid search
│
├── scripts/                  # Utility scripts
│   ├── generate_product_images.py  # DALL-E image generation
│   └── init_databases.py    # Database initialization
│
├── db/                       # Database initialization scripts
│   ├── sqlserver/init.sql
│   ├── postgres/init.sql
│   └── mongo/init.js
│
├── presentation.html         # Slide deck for demo presentation
├── mcp_config.json          # MCP servers configuration
└── requirements.txt
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- Azure CLI logged in (`az login`)
- Azure subscription with:
  - Azure SQL Database
  - Azure Database for PostgreSQL (with pgvector)
  - Azure Cosmos DB for MongoDB vCore
  - Azure Cosmos DB NoSQL (activity tracking)
  - Azure OpenAI (text-embedding-3-large, gpt-4o)

### 2. Environment Setup

```bash
# Clone the repository
git clone <repository-url>
cd flask-multi-db-monorepo

all the code is in the zip code.zip , unzip to get access

# Create virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file:

```ini
# Azure SQL (Products) - SQL authentication
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=productcatalog
AZURE_SQL_USER=your-sql-user
AZURE_SQL_PASSWORD=your-sql-password

# PostgreSQL (Orders)
POSTGRES_HOST=your-server.postgres.database.azure.com
POSTGRES_DATABASE=ordersdb
POSTGRES_USER=your-username
POSTGRES_PASSWORD=your-password

# MongoDB vCore (Logistics)
MONGODB_HOST=your-cluster.mongocluster.cosmos.azure.com
MONGODB_DATABASE=logisticsdb
MONGODB_USER=your-username
MONGODB_PASSWORD=your-password

# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o

# Cosmos DB NoSQL (Activity Tracking)
COSMOS_NOSQL_ENDPOINT=https://your-account.documents.azure.com:443/
COSMOS_NOSQL_KEY=your-key
COSMOS_NOSQL_DATABASE=useractivities
COSMOS_NOSQL_CONTAINER=daily_activities


# Azure AI Translator
AZURE_TRANSLATOR_ENDPOINT=https://your-account.cognitiveservices.azure.com
AZURE_TRANSLATOR_KEY=your-key
AZURE_TRANSLATOR_REGION=your-Region

# App Configuration
SECRET_KEY=your-secret-key-for-sessions
```

### 4. Initialize Databases

```bash
python scripts/init_databases.py
```

### 5. Run the Application

```bash
cd unified_app
python app.py
```

Access at: **http://localhost:5000**

## 🔄 Application Workflow

```
┌─────────────────────────────────────────────────────────────────┐
│                      UNIFIED FLASK APP                          │
│                       (Port 5000)                               │
├─────────────────────────────────────────────────────────────────┤
│  📦 Products    │  📋 Orders      │  🚚 Logistics  │  📊 Activity  │
│  /products      │  /customers     │  /deliveries   │  /activities  │
│  /catalog       │  /orders        │  /partners     │  (audit log)  │
│                 │                 │  /dispatch     │              │
├─────────────────────────────────────────────────────────────────┤
│                    💬 AI Query Interface                        │
│                        /ask                                     │
│     PostgreSQL │ MongoDB │ Azure SQL │ Cosmos DB NoSQL          │
└─────────────────────────────────────────────────────────────────┘
         │                │                │                │
         ▼                ▼                ▼                ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐
│  Azure SQL  │  │ PostgreSQL  │  │   MongoDB   │  │ Cosmos DB    │
│  Products   │  │   Orders    │  │  Logistics  │  │ NoSQL        │
│  VECTOR     │  │  DiskANN    │  │ cosmosSearch│  │ Activities   │
└─────────────┘  └─────────────┘  └─────────────┘  └──────────────┘
         │                │                │                │
         └────────────────┼────────────────┴────────────────┘
                          ▼
              ┌─────────────────────┐
              │    Azure OpenAI     │
              │  Embeddings + GPT-4o│
              └─────────────────────┘
```

## 🔌 MCP Servers

Configure MCP servers for AI agent integration in `.vscode/mcp.json` or use the provided `mcp_config.json`:

```json
{
  "mcpServers": {
    "postgres-orders": {
      "command": "python",
      "args": ["mcp_postgres_server/server.py"]
    },
    "mongodb-logistics": {
      "command": "python",
      "args": ["mcp_mongo_server/server.py"]
    },
    "azuresql-products": {
      "command": "python",
      "args": ["mcp_sql_server/server.py"]
    },
    "cosmosdb-activities": {
      "command": "python",
      "args": ["mcp_cosmos_server/server.py"]
    }
  }
}
```

### Available MCP Tools

| Server | Tools |
|--------|-------|
| **azuresql-products** | `get_database_schema`, `execute_query`, `search_products`, `get_low_stock_products`, `get_statistics` |
| **postgres-orders** | `get_database_schema`, `execute_query`, `search_customers`, `get_customer_orders`, `get_statistics` |
| **mongodb-logistics** | `get_database_schema`, `query_collection`, `get_delivery_status`, `search_partners` |
| **cosmosdb-activities** | `get_database_schema`, `execute_query`, `get_sample_documents`, `get_statistics`, `get_user_activities`, `get_activities_for_day`, `get_distinct_users` |

## 🎯 Demo Features

### Product Catalog (Azure SQL)
- Category filtering and price range
- Vector-based semantic search
- Stock management with low-stock alerts
- Natural language queries for products

### Order Management (PostgreSQL)
- Customer CRUD operations
- Multi-item order creation
- Status tracking (pending → confirmed → processing → shipped → delivered)
- Auto-creates delivery record in MongoDB when order is placed

### Logistics (MongoDB)
- **Dispatch Center**: View unassigned deliveries
- **Partner Management**: Assign deliveries to partners
- **Delivery Tracking**: Public tracking page (no login required)
- **Status Updates**: in_transit, out_for_delivery, delivered

### Activity Tracking (Cosmos DB NoSQL)
- **Per-user daily activity documents** partitioned by email
- **Audit log UI** at `/activities` with date and email filters
- **Composite index** on email + date for efficient queries
- **NL queries**: "Who logged in today?", "Most active user?"
- **MCP server** for AI agent integration

## �️ Product Image Generation

Automatically generate product images using **Azure OpenAI DALL-E 3**, upload them to **Azure Blob Storage**, and update the database.

### Setup

Add these environment variables to your `.env`:

```ini
# Azure Storage (for product images)
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
# OR
AZURE_STORAGE_ACCOUNT=your-storage-account
AZURE_STORAGE_KEY=your-storage-key

AZURE_STORAGE_CONTAINER=product-images

# Azure OpenAI DALL-E
AZURE_OPENAI_DALLE_DEPLOYMENT=dall-e-3
```

### Usage

```bash
cd flask-multi-db-monorepo

# Preview what would be generated (no changes)
python scripts/generate_product_images.py --dry-run

# Generate images for all products without images
python scripts/generate_product_images.py

# Limit to first N products
python scripts/generate_product_images.py --limit 5

# Adjust delay between API calls (default: 5 seconds)
python scripts/generate_product_images.py --delay 10
```

### How It Works

```
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│   Azure SQL      │    │   DALL-E 3       │    │   Blob Storage   │
│   products       │───▶│   Generate       │───▶│   Upload PNG     │
│   (no image)     │    │   1024x1024      │    │   (private)      │
└──────────────────┘    └──────────────────┘    └──────────────────┘
         │                                               │
         └──────────── UPDATE image_url ◀────────────────┘
```

1. **Query**: Fetches products without `image_url` from Azure SQL
2. **Generate**: Creates professional product photography prompt for DALL-E 3
3. **Download**: Retrieves the generated image from temporary URL
4. **Upload**: Stores image in Azure Blob Storage (`products/{sku}.png`)
5. **Update**: Sets `image_url` column in the products table

### Private Container Access

Images are stored in a **private blob container** (no public access required). The Flask app serves images through a proxy endpoint:

```
GET /api/products/{sku}/image
```

**How the proxy works:**
- Flask fetches the blob using your storage credentials
- Returns the image with proper `Content-Type` and caching headers
- No SAS tokens or public URLs needed in the database
- Browser caches images for 1 day

**Benefits:**
- ✅ No public blob access required
- ✅ Leverages existing Azure credentials
- ✅ Works with private endpoints and VNet
- ✅ Centralized access control via Flask auth

### Regenerating URLs

If you need to regenerate SAS URLs for existing images (without calling DALL-E again):

```bash
python scripts/generate_product_images.py --regenerate-urls
```

## �📊 Presentation

Open the slide deck for demo presentations:

```bash
# Open in browser
start presentation.html
```

10 slides covering architecture, workflow, and technology stack.

## 🧪 Testing

```bash
pytest tests/
```

## 🔧 Technical Details

### Vector Search Comparison

| Database | Vector Type | Index | Distance Function |
|----------|-------------|-------|-------------------|
| Azure SQL | `VECTOR(1536)` | Scan | `VECTOR_DISTANCE('cosine', ...)` |
| PostgreSQL | `vector(3072)` | DiskANN | `<=>` |
| MongoDB | Array | cosmosSearch | vectorSearch pipeline |

### Natural Language → Query Flow

```
User Question
     │
     ▼
┌──────────────────┐
│  Azure OpenAI    │
│    GPT-4o        │
│                  │
│  System prompt   │
│  + DB schema     │
└────────┬─────────┘
         │
         ▼
  Generated Query
  (SQL / MongoDB / Cosmos SQL)
         │
         ▼
┌──────────────────┐
│  Safety Check    │
│  (SELECT only)   │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Execute Query   │
│  Return Results  │
└──────────────────┘
```

## 📄 License

MIT License

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request


