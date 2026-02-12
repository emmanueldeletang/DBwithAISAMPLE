# Demo Database AI - Azure Infrastructure

This Bicep template deploys a complete database demo environment in Azure with:

## Resources Created

| Resource | Name Pattern | Description |
|----------|-------------|-------------|
| **Resource Group** | `RG-demo-database-ai-{extraName}` | Contains all resources |
| **Azure SQL Server** | `demodbai{extraName}-sqlserver` | Azure SQL Database logical server |
| **SQL Database** | `demodbai{extraName}-sqldb` | Basic tier SQL Database (2GB) |
| **PostgreSQL Flexible Server** | `demodbai{extraName}-postgres` | PostgreSQL v16 Flexible Server |
| **PostgreSQL Database** | `demodbai{extraName}db` | UTF8 database |
| **Cosmos DB MongoDB vCore** | `demodbai{extraName}-cosmosdb-mongo` | MongoDB vCore cluster (M30) |

## Prerequisites

- Azure CLI installed and logged in
- Azure subscription with appropriate permissions
- Bicep CLI (included with Azure CLI v2.20+)

## Deployment

### Option 1: Using Azure CLI with parameters file

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

## Clean Up

To delete all resources:

```bash
az group delete --name RG-demo-database-ai-{extraName} --yes --no-wait
```

## File Structure

```
demodatabasedaysmars2026/
├── main.bicep           # Main deployment template (subscription scope)
├── main.bicepparam      # Parameters file
├── README.md            # This file
└── modules/
    └── databases.bicep  # Database resources module
```

## Notes

- All resources are deployed with public access enabled for demo purposes
- Azure services are allowed to access all databases via firewall rules
- For production use, consider enabling private endpoints and disabling public access
- Cosmos DB MongoDB vCore uses M30 tier - adjust based on your needs
