# Demo Database AI - Multi-Database Azure Application

This project deploys a complete multi-database demo environment in Azure and includes a **unified Flask web application** that showcases Azure SQL, PostgreSQL, and Azure Cosmos DB for MongoDB working together.

## Overview

```
┌───────────────────────────────────────────────────────────────┐
│             Unified Flask App (Port 5000)                     │
│   i18n: English · Français · Deutsch · Vlaams · Español · IT │
├───────────┬───────────────┬───────────────┬───────────────────┤
│ Products  │ Orders &      │ Logistics     │ Inventory Agent   │
│ + Vector  │ Customers     │ Deliveries    │ (cross-DB)        │
│ Search    │ + Stock mgmt  │ Partners      │                   │
├───────────┼───────────────┼───────────────┼───────────────────┤
│ Azure SQL │  PostgreSQL   │    MongoDB    │ SQL → Mongo       │
│ (VECTOR)  │  (pgvector)   │  (Cosmos DB)  │ (reorders)        │
└───────────┴───────────────┴───────────────┴───────────────────┘
```

### Application Features

- **Multi-language UI** — 6 languages (EN/FR/DE/NL/ES/IT), selectable on login page and navbar
- **Product Catalog** (Azure SQL) — CRUD, vector semantic search, AI image generation (DALL-E 3)
- **Orders & Customers** (PostgreSQL) — Order creation with automatic stock decrement and delivery creation
- **Logistics** (Cosmos DB for MongoDB) — Delivery tracking, dispatch center, partner CRUD + search
- **Inventory Agent** — Cross-database: reads stock from Azure SQL, creates reorders in MongoDB, fulfill to restock
- **AI Natural Language Queries** — Ask questions across all 3 databases via GPT-4o
- **Local Authentication** — Email/password with bcrypt, session-based, login audit log
- **User Management** — Admin UI for user CRUD and password changes

## Azure Resources Created

| Resource | Name Pattern | Description |
|----------|-------------|-------------|
| **Resource Group** | `RG-demo-database-ai-{extraName}` | Contains all resources |
| **Azure SQL Server** | `demodbai{extraName}-sqlserver` | Azure SQL Database logical server |
| **SQL Database** | `demodbai{extraName}-sqldb` | Basic tier SQL Database (2GB) |
| **PostgreSQL Flexible Server** | `demodbai{extraName}-postgres` | PostgreSQL v16 Flexible Server |
| **PostgreSQL Database** | `demodbai{extraName}db` | UTF8 database |
| **Cosmos DB MongoDB vCore** | `demodbai{extraName}-cosmosdb-mongo` | MongoDB vCore cluster (M30) |
| **Storage Account** | `demoaist{suffix}` | StorageV2, Standard_LRS, Hot tier |
| **Blob Container** | `product-images` | Private container for product images |
| **App Service** | `multidatabase-demo-app` | B1 Linux plan, Python 3.12 |

## Prerequisites

- Azure CLI installed and logged in
- Azure subscription with appropriate permissions
- Bicep CLI (included with Azure CLI v2.20+)

## Deployment

### Option 1: PowerShell Script (Recommended)

The easiest way to deploy all resources:

```powershell
# Deploy with defaults (francecentral region)
.\\deploy-databases.ps1

# Custom subscription/resource group
.\\deploy-databases.ps1 -SubscriptionId "your-sub-id" -ResourceGroup "mygroup" -Location "westeurope"
```

This creates all resources and saves connection strings to `.env.azure`.

### Option 2: Using Azure CLI with parameters file

1. Edit `main.bicepparam` and replace placeholder values:
   - `<your-extra-name>`: Your unique identifier
   - `<your-sql-password>`: SQL Server password
   - `<your-postgres-password>`: PostgreSQL password
   - `<your-cosmos-password>`: Cosmos DB password

2. Deploy:
```bash
az deployment sub create \
  --location westeurope \
  --template-file main.bicep \
  --parameters main.bicepparam
```

### Option 2: Using Azure CLI with inline parameters

```bash
az deployment sub create \
  --location westeurope \
  --template-file main.bicep \
  --parameters extraName='myproject' \
               sqlAdminPassword='YourSecurePassword123!' \
               postgresAdminPassword='YourSecurePassword123!' \
               cosmosAdminPassword='YourSecurePassword123!'
```

### Option 3: Using PowerShell

```powershell
New-AzSubscriptionDeployment `
  -Location "westeurope" `
  -TemplateFile "main.bicep" `
  -extraName "myproject" `
  -sqlAdminPassword (ConvertTo-SecureString "YourSecurePassword123!" -AsPlainText -Force) `
  -postgresAdminPassword (ConvertTo-SecureString "YourSecurePassword123!" -AsPlainText -Force) `
  -cosmosAdminPassword (ConvertTo-SecureString "YourSecurePassword123!" -AsPlainText -Force)
```

## Password Requirements

All passwords must meet Azure complexity requirements:
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

## Connection Strings

After deployment, you can connect to the databases using:

### SQL Server
```
Server=demodbai{extraName}-sqlserver.database.windows.net;Database=demodbai{extraName}-sqldb;User Id={sqlAdminLogin};Password={password};
```

### PostgreSQL
```
Host=demodbai{extraName}-postgres.postgres.database.azure.com;Database=demodbai{extraName}db;Username={postgresAdminLogin};Password={password};SSL Mode=Require;
```

### Cosmos DB MongoDB
The connection string is available in the deployment outputs or Azure Portal.

### Azure Storage Account (Product Images)

The storage account is created with the following configuration:
- **Kind**: StorageV2
- **SKU**: Standard_LRS
- **Access Tier**: Hot
- **Public blob access**: Disabled
- **Min TLS**: 1.2
- **Container**: `product-images` (private)

Connection details are saved to `.env.azure`:
```
AZURE_STORAGE_ACCOUNT=demoaist{suffix}
AZURE_STORAGE_KEY=<auto-generated>
AZURE_STORAGE_CONTAINER=product-images
```

Blob endpoint:
```
https://demoaist{suffix}.blob.core.windows.net
```

## Outputs

The deployment returns:
- `resourceGroupName`: Name of the created resource group
- `resourceGroupId`: Resource ID of the resource group
- `sqlServerName`: SQL Server name
- `sqlServerFqdn`: SQL Server fully qualified domain name
- `sqlDatabaseName`: SQL Database name
- `postgresServerName`: PostgreSQL server name
- `postgresServerFqdn`: PostgreSQL fully qualified domain name
- `cosmosDbName`: Cosmos DB MongoDB cluster name
- `cosmosDbConnectionString`: Cosmos DB connection string
- `storageAccountName`: Storage account name (for product images)
- `storageContainerName`: Blob container name (`product-images`)

## Clean Up

To delete all resources:

```bash
az group delete --name RG-demo-database-ai-{extraName} --yes --no-wait
```

## File Structure

```
demodatabasedaysmars2026/
├── deploy-databases.ps1          # PowerShell infra deployment (Bicep)
├── main.bicep                    # Main Bicep template (subscription scope)
├── main.bicepparam               # Parameters file
├── README.md                     # This file
├── modules/
│   └── databases.bicep           # Database resources module
└── flask-multi-db-monorepo/      # Flask application
    ├── .env                      # Environment variables (local)
    ├── requirements.txt          # Python dependencies
    ├── deploy-webapp.ps1         # App Service deployment (Kudu API)
    ├── seed_users.py             # Seed default user accounts
    ├── unified_app/              # Main application
    │   ├── app.py                # Flask routes (all features)
    │   ├── translations.py       # i18n – 6 languages
    │   ├── services/
    │   │   ├── user_service.py   # User auth + CRUD (PostgreSQL)
    │   │   └── inventory_agent.py # Stock agent (Azure SQL → MongoDB)
    │   └── templates/            # Jinja2 templates (Bootstrap 5)
    ├── product_app/services/     # ProductService (Azure SQL)
    ├── order_app/services/       # OrderService (PostgreSQL)
    ├── logistics_app/services/   # Delivery/Partner services (MongoDB)
    ├── shared/                   # Config, embeddings, search utilities
    ├── db/                       # Database init scripts (SQL, Mongo)
    └── scripts/                  # Setup & test scripts
```

## Notes

- All resources are deployed with public access enabled for demo purposes
- Azure services are allowed to access all databases via firewall rules
- For production use, consider enabling private endpoints and disabling public access
- Cosmos DB MongoDB vCore uses M30 tier — adjust based on your needs
- Storage account has public blob access disabled — use storage key or SAS tokens
- App deployed via Kudu API with publishing credentials (basic auth)
