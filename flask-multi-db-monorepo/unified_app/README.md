# Unified Multi-Database Demo Application

A single Flask application that combines three Azure database services into one unified demo, with multi-language UI, an inventory agent, and AI-powered natural language queries.

- **Azure SQL** — Product Catalog with Vector Search
- **PostgreSQL** — Orders, Customer Management & User Accounts
- **Azure Cosmos DB for MongoDB** — Logistics, Deliveries, Partners & Reorders

## Features

### Multi-Language UI (i18n)
- **6 languages**: English, Français, Deutsch, Vlaams (Flemish), Español, Italiano
- Language selector on the login page and in the top navigation bar
- Language preference stored in session — persists across pages
- All UI labels, buttons, messages, and navigation are translated

### Authentication & Users
- **Local email/password** authentication with **bcrypt** password hashing
- User accounts stored in **PostgreSQL** (`app_users` table)
- Session-based management with `flask-session`
- Admin UI: create, edit, delete users, change passwords, active/inactive status
- Login audit log stored in **MongoDB**

### Product Management (Azure SQL)
- Full CRUD on the product catalog
- **Vector Search** using Azure SQL's native `VECTOR(1536)` type
- OpenAI `text-embedding-3-large` embeddings for semantic product search
- `VECTOR_DISTANCE` with cosine similarity
- AI-generated product images via DALL-E 3 stored in Azure Blob Storage
- **Stock management** — stock is automatically decremented when orders are placed

### Order Management (PostgreSQL)
- Customer CRUD (create, edit, delete)
- Order creation with automatic delivery record in MongoDB
- Order status tracking (pending → confirmed → shipped → delivered)
- Stock decrement in Azure SQL on order creation

### Logistics (Azure Cosmos DB for MongoDB)
- Delivery tracking with status updates
- Dispatch center for pending deliveries
- Partner management — full CRUD + search (regex across name, email, phone, areas, vehicles)
- Package tracking (public, no login required)
- **AI-powered Natural Language Queries** via Azure OpenAI GPT-4o

### Inventory Agent
- Cross-database agent: reads product stock from **Azure SQL**, creates reorder documents in **MongoDB**
- Configurable threshold (default: stock < 10) and reorder quantity (default: 50 units)
- **Fulfill reorder** button: marks a reorder as received and adds stock back to Azure SQL
- Can be run via UI, API, or CLI (`python -m unified_app.services.inventory_agent`)

## Quick Start

### 1. Install Dependencies

```bash
cd flask-multi-db-monorepo
pip install -r requirements.txt
```

### 2. Configure Environment

Create a `.env` file in the `flask-multi-db-monorepo` folder:

```env
# Azure SQL (Product Catalog)
AZURE_SQL_SERVER=your-server.database.windows.net
AZURE_SQL_DATABASE=your-database
AZURE_SQL_USER=your-sql-user
AZURE_SQL_PASSWORD=your-sql-password

# PostgreSQL (Customers, Orders, Users)
POSTGRES_HOST=your-postgres.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DATABASE=your-database
POSTGRES_USER=your-user
POSTGRES_PASSWORD=your-password

# MongoDB / Azure Cosmos DB for MongoDB (Logistics)
MONGODB_HOST=your-cluster.mongocluster.cosmos.azure.com
MONGODB_USER=your-user
MONGODB_PASSWORD=your-password
MONGODB_DATABASE=logisticsdb

# Azure OpenAI (Embeddings + Chat)
AZURE_OPENAI_ENDPOINT=https://your-instance.openai.azure.com
AZURE_OPENAI_API_KEY=your-key
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_EMBEDDING_DIMENSION=1536
AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o

# Azure Storage (Product Images)
AZURE_STORAGE_CONNECTION_STRING=your-connection-string

# DALL-E 3 (Image Generation)
AZURE_OPENAI_DALLE_DEPLOYMENT=dall-e-3

# Flask
SECRET_KEY=your-secret-key
FLASK_ENV=development
FLASK_DEBUG=1
```

### 3. Seed Users

```bash
python seed_users.py
```

Creates 4 default users (Emmanuel, Richard Prade, Nadia, Myrrhine) with password `Password12/34`.

### 4. Run the Application

```bash
cd unified_app
python app.py
```

The application starts at `http://localhost:5000`.

## Application Structure

```
unified_app/
├── app.py                    # Main Flask application (all routes)
├── translations.py           # i18n – 6 languages (en/fr/de/nl/es/it)
├── requirements.txt          # Python dependencies
├── README.md                 # This file
├── services/
│   ├── user_service.py       # User CRUD + bcrypt auth (PostgreSQL)
│   └── inventory_agent.py    # Stock check agent (Azure SQL → MongoDB)
└── templates/
    ├── base.html             # Base layout with sidebar + navbar + i18n
    ├── dashboard.html        # Main dashboard with stats
    ├── ask.html              # AI natural language query interface
    ├── auth/
    │   └── login.html        # Login page with language selector
    ├── users/
    │   ├── list.html         # User list
    │   ├── form.html         # Create/Edit user
    │   └── password.html     # Change password
    ├── products/
    │   ├── list.html         # Product catalog with filters
    │   ├── detail.html       # Product details + AI image
    │   ├── form.html         # Add/Edit product
    │   └── search.html       # Vector search
    ├── orders/
    │   ├── list.html         # Order list with status filter
    │   ├── detail.html       # Order details + items
    │   └── create.html       # Create order (multi-product)
    ├── customers/
    │   ├── list.html         # Customer list
    │   └── detail.html       # Customer details + order history
    ├── deliveries/
    │   ├── list.html         # Delivery list
    │   ├── detail.html       # Delivery details + status timeline
    │   ├── dispatch.html     # Dispatch center
    │   └── track.html        # Public tracking (no auth)
    ├── partners/
    │   ├── list.html         # Partner list
    │   ├── detail.html       # Partner details
    │   ├── form.html         # Add/Edit partner
    │   └── search.html       # Partner search
    ├── inventory/
    │   └── index.html        # Stock dashboard + reorder history
    └── audit/
        └── list.html         # Login audit log
```

## Routes

### Authentication & Language
| Route | Method | Description |
|-------|--------|-------------|
| `/login` | GET/POST | Login page with language selector |
| `/logout` | GET | Logout |
| `/set-language/<lang>` | GET | Switch UI language (en/fr/de/nl/es/it) |

### User Management (Admin)
| Route | Method | Description |
|-------|--------|-------------|
| `/users` | GET | User list |
| `/users/create` | GET/POST | Create user |
| `/users/<id>/edit` | GET/POST | Edit user |
| `/users/<id>/password` | GET/POST | Change password |
| `/users/<id>/delete` | POST | Delete user |
| `/audit` | GET | Login audit log |

### Dashboard
| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main dashboard with cross-database stats |

### Products (Azure SQL)
| Route | Method | Description |
|-------|--------|-------------|
| `/products` | GET | Product list with category/stock filters |
| `/products/<sku>` | GET | Product details |
| `/products/add` | GET/POST | Add product |
| `/products/<sku>/edit` | GET/POST | Edit product |
| `/products/<sku>/delete` | POST | Delete product |
| `/products/search` | GET | Vector semantic search |

### Orders (PostgreSQL)
| Route | Method | Description |
|-------|--------|-------------|
| `/orders` | GET | Order list with status filter |
| `/orders/<id>` | GET | Order details + items |
| `/orders/create` | GET/POST | Create order (decrements stock) |
| `/orders/<id>/status` | POST | Update order status |

### Customers (PostgreSQL)
| Route | Method | Description |
|-------|--------|-------------|
| `/customers` | GET | Customer list |
| `/customers/<id>` | GET | Customer details + order history |
| `/customers/add` | GET/POST | Add customer |
| `/customers/<id>/edit` | GET/POST | Edit customer |
| `/customers/<id>/delete` | POST | Delete customer |

### Deliveries (MongoDB)
| Route | Method | Description |
|-------|--------|-------------|
| `/deliveries` | GET | Delivery list |
| `/deliveries/<id>` | GET | Delivery details |
| `/deliveries/dispatch` | GET | Dispatch center |
| `/deliveries/<id>/dispatch` | POST | Dispatch delivery to partner |
| `/deliveries/<id>/status` | POST | Update delivery status |
| `/track` | GET | Public tracking (no auth required) |

### Partners (MongoDB)
| Route | Method | Description |
|-------|--------|-------------|
| `/partners` | GET | Partner list |
| `/partners/<id>` | GET | Partner details |
| `/partners/add` | GET/POST | Add partner |
| `/partners/<id>/edit` | GET/POST | Edit partner |
| `/partners/<id>/delete` | POST | Delete partner |
| `/partners/search` | GET | Search partners |

### Inventory Agent
| Route | Method | Description |
|-------|--------|-------------|
| `/inventory` | GET | Stock dashboard + reorder history |
| `/inventory/check` | POST | Run inventory check (creates reorders) |
| `/inventory/reorder/<id>/fulfill` | POST | Mark reorder received + add stock |

### AI Queries
| Route | Method | Description |
|-------|--------|-------------|
| `/ask` | GET/POST | Natural language query interface |
| `/api/ask` | POST | API endpoint for NL queries |

## API Endpoints

```bash
# List all products
GET /api/products

# Get product by SKU
GET /api/products/<sku>

# Get / generate product image
GET  /api/products/<sku>/image
POST /api/products/<sku>/generate-image

# Create delivery
POST /api/deliveries
Content-Type: application/json
{
  "order_id": "uuid",
  "customer_name": "John Doe",
  "address": "123 Main St",
  "city": "Paris"
}

# Natural language query
POST /api/ask
Content-Type: application/json
{ "question": "How many pending deliveries are there?" }

# Inventory agent (JSON)
POST /api/inventory/check
GET  /api/inventory/reorders?status=pending&limit=50
```

## Architecture

```
┌───────────────────────────────────────────────────────────────┐
│                   Unified Flask App (Port 5000)               │
│  i18n: en · fr · de · nl · es · it                            │
├───────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌─────────┐ │
│  │ Products   │  │  Orders    │  │ Logistics  │  │Inventory│ │
│  │  Routes    │  │  Routes    │  │  Routes    │  │  Agent  │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └────┬────┘ │
│        │               │               │              │      │
│  ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐  ┌───▼────┐ │
│  │  Product   │  │  Order     │  │  Delivery  │  │ Stock  │ │
│  │  Service   │  │  Service   │  │  Service   │  │ Check  │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └───┬────┘ │
└────────┼───────────────┼───────────────┼──────────────┼──────┘
         │               │               │              │
   ┌─────▼──────┐  ┌─────▼──────┐  ┌─────▼──────┐      │
   │  Azure SQL │  │ PostgreSQL │  │  MongoDB   │◄─────┘
   │  (VECTOR)  │  │ (pgvector) │  │ (Cosmos DB)│  reorders
   │  Products  │  │  Orders    │  │ Deliveries │
   │  Stock ◄───┼──┤  Customers │  │ Partners   │
   │            │  │  Users     │  │ Audit Logs │
   └────────────┘  └────────────┘  └────────────┘
```

### Cross-Database Flows

- **Order creation**: PostgreSQL (order) → Azure SQL (decrement stock) → MongoDB (create delivery)
- **Inventory agent**: Azure SQL (read stock) → MongoDB (create reorder)
- **Fulfill reorder**: MongoDB (update status) → Azure SQL (increase stock)
- **Login audit**: PostgreSQL (authenticate) → MongoDB (log event)

## Deployment

Deploy to Azure App Service using the included script:

```bash
.\deploy-webapp.ps1
```

The script creates/updates the App Service, configures environment variables, packages the app, and deploys via the Kudu API.

## License

MIT
