#===============================================================================
# Azure Database Services Provisioning Script
# Creates: Azure SQL, PostgreSQL Flexible Server, Cosmos DB for MongoDB vCore
#===============================================================================

param(
    [string]$SubscriptionId = "747112cf-d2bc-49fa-9001-e8602a3c8a0e",
    [string]$ResourceGroup = "demoai",
    [string]$Location = "francecentral",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# =============================================================================
# CONFIGURATION
# =============================================================================
$RandomSuffix = -join ((97..122) | Get-Random -Count 6 | ForEach-Object { [char]$_ })

# Azure SQL Configuration (Entra ID Only - No SQL Auth)
$AzureSqlServerName = "demoai-sql-$RandomSuffix"
$AzureSqlDbName = "productcatalog"
# Entra ID admin will be configured with current user
$AzureSqlEntraIdOnly = $true  # Set to $false to also enable SQL auth

# PostgreSQL Configuration
$PostgresServerName = "demoai-pg-$RandomSuffix"
$PostgresDbName = "ordersdb"
$PostgresAdminUser = "pgadmin"
$PostgresAdminPassword = "Demo@2026!Pg$RandomSuffix"

# Cosmos DB for MongoDB vCore Configuration
$CosmosDbClusterName = "demoai-mongo-$RandomSuffix"
$CosmosDbAdminUser = "mongoadmin"
$CosmosDbAdminPassword = "Demo@2026!Mongo$RandomSuffix"

# Azure Storage Account Configuration (for product images)
$StorageAccountName = "demoaist$RandomSuffix"
$StorageContainerName = "product-images"

# Output file
$OutputFile = Join-Path $PSScriptRoot ".env.azure"

# =============================================================================
# FUNCTIONS
# =============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host $Message -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Yellow
}

# =============================================================================
# PRE-CHECKS
# =============================================================================

Write-Step "Checking Azure CLI"

try {
    $azVersion = az version --output json 2>$null | ConvertFrom-Json
    Write-Success "Azure CLI version: $($azVersion.'azure-cli')"
}
catch {
    Write-Host "[ERROR] Azure CLI not found. Install from: https://aka.ms/installazurecli" -ForegroundColor Red
    exit 1
}

# =============================================================================
# AZURE LOGIN & SUBSCRIPTION
# =============================================================================

Write-Step "Connecting to Azure"

# Check if logged in
$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Info "Logging in to Azure..."
    az login
}
else {
    Write-Success "Already logged in as: $($account.user.name)"
}

# Set subscription
Write-Info "Setting subscription: $SubscriptionId"
az account set --subscription $SubscriptionId
Write-Success "Subscription set"

# =============================================================================
# RESOURCE GROUP
# =============================================================================

Write-Step "Creating Resource Group: $ResourceGroup"

$rgExists = az group exists --name $ResourceGroup
if ($rgExists -eq "true") {
    Write-Info "Resource group already exists"
}
else {
    az group create --name $ResourceGroup --location $Location --output none
    Write-Success "Resource group created"
}

# =============================================================================
# GET CURRENT USER IDENTITY FOR ENTRA ID
# =============================================================================

Write-Step "Getting Current User Identity for Entra ID"

$currentUser = az ad signed-in-user show --output json 2>$null | ConvertFrom-Json
if (-not $currentUser) {
    Write-Host "[ERROR] Could not get current user identity. Make sure you're logged in with 'az login'" -ForegroundColor Red
    exit 1
}

$EntraIdAdminName = $currentUser.userPrincipalName
$EntraIdAdminObjectId = $currentUser.id
Write-Success "Current user: $EntraIdAdminName"
Write-Success "Object ID: $EntraIdAdminObjectId"

# =============================================================================
# AZURE SQL DATABASE (ENTRA ID AUTHENTICATION)
# =============================================================================

Write-Step "Creating Azure SQL Server & Database (Entra ID Only)"

Write-Info "Creating SQL Server: $AzureSqlServerName"

if ($AzureSqlEntraIdOnly) {
    # Create server with Entra ID only (no SQL auth), using external admin
    az sql server create `
        --name $AzureSqlServerName `
        --resource-group $ResourceGroup `
        --location $Location `
        --enable-ad-only-auth `
        --external-admin-principal-type "User" `
        --external-admin-name $EntraIdAdminName `
        --external-admin-sid $EntraIdAdminObjectId `
        --output none
    Write-Success "SQL Server created with Entra ID only authentication"
}
else {
    # Create server with both SQL and Entra ID auth
    $AzureSqlAdminUser = "sqladmin"
    $AzureSqlAdminPassword = "Demo@2026!Sql$RandomSuffix"
    
    az sql server create `
        --name $AzureSqlServerName `
        --resource-group $ResourceGroup `
        --location $Location `
        --admin-user $AzureSqlAdminUser `
        --admin-password $AzureSqlAdminPassword `
        --output none
    
    # Set Entra ID admin
    Write-Info "Configuring Entra ID administrator..."
    az sql server ad-admin create `
        --resource-group $ResourceGroup `
        --server-name $AzureSqlServerName `
        --display-name $EntraIdAdminName `
        --object-id $EntraIdAdminObjectId `
        --output none
    Write-Success "SQL Server created with SQL + Entra ID authentication"
}

Write-Info "Configuring firewall (Allow Azure Services)..."
az sql server firewall-rule create `
    --resource-group $ResourceGroup `
    --server $AzureSqlServerName `
    --name "AllowAzureServices" `
    --start-ip-address 0.0.0.0 `
    --end-ip-address 0.0.0.0 `
    --output none

# Add current IP
try {
    $myIp = (Invoke-RestMethod -Uri "https://api.ipify.org" -TimeoutSec 5)
    az sql server firewall-rule create `
        --resource-group $ResourceGroup `
        --server $AzureSqlServerName `
        --name "AllowMyIP" `
        --start-ip-address $myIp `
        --end-ip-address $myIp `
        --output none
    Write-Info "Added firewall rule for IP: $myIp"
}
catch {
    Write-Info "Could not add current IP to firewall"
}

Write-Info "Creating database: $AzureSqlDbName"
az sql db create `
    --resource-group $ResourceGroup `
    --server $AzureSqlServerName `
    --name $AzureSqlDbName `
    --edition "Standard" `
    --service-objective "S2" `
    --output none

Write-Success "Azure SQL created: $AzureSqlServerName.database.windows.net"

# =============================================================================
# POSTGRESQL FLEXIBLE SERVER
# =============================================================================

Write-Step "Creating PostgreSQL Flexible Server"

Write-Info "Creating PostgreSQL Server: $PostgresServerName (this may take 5-10 minutes)..."
az postgres flexible-server create `
    --name $PostgresServerName `
    --resource-group $ResourceGroup `
    --location $Location `
    --admin-user $PostgresAdminUser `
    --admin-password $PostgresAdminPassword `
    --sku-name "Standard_B1ms" `
    --tier "Burstable" `
    --version "16" `
    --storage-size 32 `
    --public-access 0.0.0.0-255.255.255.255 `
    --yes `
    --output none

Write-Info "Creating database: $PostgresDbName"
az postgres flexible-server db create `
    --resource-group $ResourceGroup `
    --server-name $PostgresServerName `
    --database-name $PostgresDbName `
    --output none

Write-Info "Enabling extensions (pg_trgm, vector, uuid-ossp)..."
az postgres flexible-server parameter set `
    --resource-group $ResourceGroup `
    --server-name $PostgresServerName `
    --name azure.extensions `
    --value "pg_trgm,vector,uuid-ossp" `
    --output none

Write-Success "PostgreSQL created: $PostgresServerName.postgres.database.azure.com"

# =============================================================================
# COSMOS DB FOR MONGODB VCORE
# =============================================================================

Write-Step "Creating Cosmos DB for MongoDB vCore"

# Check/install extension
$extensions = az extension list --output json | ConvertFrom-Json
if (-not ($extensions | Where-Object { $_.name -eq "cosmosdb-preview" })) {
    Write-Info "Installing cosmosdb-preview extension..."
    az extension add --name cosmosdb-preview --yes
}

Write-Info "Creating MongoDB vCore Cluster: $CosmosDbClusterName (this may take 10-15 minutes)..."
az cosmosdb mongocluster create `
    --cluster-name $CosmosDbClusterName `
    --resource-group $ResourceGroup `
    --location $Location `
    --administrator-login $CosmosDbAdminUser `
    --administrator-login-password $CosmosDbAdminPassword `
    --server-version "7.0" `
    --shard-node-tier "M30" `
    --shard-node-disk-size-gb 32 `
    --shard-node-ha false `
    --shard-node-count 1 `
    --output none

Write-Info "Configuring firewall..."
az cosmosdb mongocluster firewall rule create `
    --cluster-name $CosmosDbClusterName `
    --resource-group $ResourceGroup `
    --rule-name "AllowAll" `
    --start-ip-address "0.0.0.0" `
    --end-ip-address "255.255.255.255" `
    --output none

Write-Success "Cosmos DB MongoDB vCore created: $CosmosDbClusterName.mongocluster.cosmos.azure.com"

# =============================================================================
# AZURE STORAGE ACCOUNT (FOR PRODUCT IMAGES)
# =============================================================================

Write-Step "Creating Azure Storage Account (for product images)"

Write-Info "Creating Storage Account: $StorageAccountName"
az storage account create `
    --name $StorageAccountName `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku "Standard_LRS" `
    --kind "StorageV2" `
    --access-tier "Hot" `
    --allow-blob-public-access false `
    --min-tls-version "TLS1_2" `
    --output none

Write-Success "Storage account created"

Write-Info "Getting storage account key..."
$StorageAccountKey = az storage account keys list `
    --resource-group $ResourceGroup `
    --account-name $StorageAccountName `
    --query "[0].value" `
    --output tsv

Write-Info "Creating container: $StorageContainerName"
az storage container create `
    --name $StorageContainerName `
    --account-name $StorageAccountName `
    --account-key $StorageAccountKey `
    --output none

Write-Success "Storage account created: $StorageAccountName.blob.core.windows.net"

# =============================================================================
# SAVE CONFIGURATION
# =============================================================================

Write-Step "Saving Configuration"

# Determine SQL auth mode for env file
if ($AzureSqlEntraIdOnly) {
    $SqlAuthSection = @"
# Azure SQL Database (Product Catalog) - ENTRA ID ONLY
AZURE_SQL_SERVER=$AzureSqlServerName.database.windows.net
AZURE_SQL_DATABASE=$AzureSqlDbName
AZURE_SQL_USE_IDENTITY=true
# Authentication: Use 'az login' then connect with ActiveDirectoryInteractive
# Entra ID Admin: $EntraIdAdminName
"@
}
else {
    $SqlAuthSection = @"
# Azure SQL Database (Product Catalog) - SQL + Entra ID Auth
AZURE_SQL_SERVER=$AzureSqlServerName.database.windows.net
AZURE_SQL_DATABASE=$AzureSqlDbName
AZURE_SQL_USER=$AzureSqlAdminUser
AZURE_SQL_PASSWORD=$AzureSqlAdminPassword
AZURE_SQL_USE_IDENTITY=true
# Entra ID Admin: $EntraIdAdminName (can also use ActiveDirectoryInteractive)
"@
}

$envContent = @"
#===============================================================================
# Azure Database Configuration - Generated $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Resource Group: $ResourceGroup | Subscription: $SubscriptionId
# Deployed by: $EntraIdAdminName
#===============================================================================

$SqlAuthSection

# PostgreSQL (Customers & Orders)
POSTGRES_HOST=$PostgresServerName.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DATABASE=$PostgresDbName
POSTGRES_USER=$PostgresAdminUser
POSTGRES_PASSWORD=$PostgresAdminPassword

# Cosmos DB for MongoDB vCore (Logistics)
MONGODB_HOST=$CosmosDbClusterName.mongocluster.cosmos.azure.com
MONGODB_USER=$CosmosDbAdminUser
MONGODB_PASSWORD=$CosmosDbAdminPassword
MONGODB_DATABASE=logisticsdb

# Azure Storage Account (Product Images)
AZURE_STORAGE_ACCOUNT=$StorageAccountName
AZURE_STORAGE_KEY=$StorageAccountKey
AZURE_STORAGE_CONTAINER=$StorageContainerName

# Azure OpenAI (configure manually)
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-large
AZURE_OPENAI_EMBEDDING_DIMENSION=3072
AZURE_OPENAI_DALLE_DEPLOYMENT=dall-e-3

# Flask Configuration
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=$(New-Guid)
"@

$envContent | Out-File -FilePath $OutputFile -Encoding UTF8
Write-Success "Configuration saved to: $OutputFile"

# =============================================================================
# SUMMARY
# =============================================================================

Write-Host "`n" -NoNewline
Write-Host "===============================================================================" -ForegroundColor Green
Write-Host "                    PROVISIONING COMPLETE!" -ForegroundColor Green
Write-Host "===============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "RESOURCES CREATED IN RESOURCE GROUP: $ResourceGroup" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Azure SQL Server (Entra ID Authentication)" -ForegroundColor Cyan
Write-Host "   Server:   $AzureSqlServerName.database.windows.net"
Write-Host "   Database: $AzureSqlDbName"
Write-Host "   Entra ID Admin: $EntraIdAdminName"
if (-not $AzureSqlEntraIdOnly) {
    Write-Host "   SQL Admin: $AzureSqlAdminUser (also available)"
}
Write-Host ""
Write-Host "2. PostgreSQL Flexible Server" -ForegroundColor Cyan
Write-Host "   Host:     $PostgresServerName.postgres.database.azure.com"
Write-Host "   Database: $PostgresDbName"
Write-Host "   User:     $PostgresAdminUser"
Write-Host ""
Write-Host "3. Cosmos DB for MongoDB vCore" -ForegroundColor Cyan
Write-Host "   Host:     $CosmosDbClusterName.mongocluster.cosmos.azure.com"
Write-Host "   User:     $CosmosDbAdminUser"
Write-Host ""
Write-Host "4. Azure Storage Account (Product Images)" -ForegroundColor Cyan
Write-Host "   Account:   $StorageAccountName"
Write-Host "   Container: $StorageContainerName"
Write-Host "   URL:       https://$StorageAccountName.blob.core.windows.net"
Write-Host ""
Write-Host "Configuration saved to: $OutputFile" -ForegroundColor Yellow
Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "  1. Run database init scripts (db/sqlserver/init.sql, etc.)"
Write-Host "  2. Configure Azure OpenAI in .env.azure"
Write-Host "  3. Copy .env.azure to .env"
Write-Host "  4. Start the Flask applications"
Write-Host ""
Write-Host "To DELETE all resources: az group delete --name $ResourceGroup --yes" -ForegroundColor Red
Write-Host "===============================================================================" -ForegroundColor Green
