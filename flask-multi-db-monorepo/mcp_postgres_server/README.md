# MCP PostgreSQL Server for Orders Database

Ce serveur MCP (Model Context Protocol) expose la base de données PostgreSQL des commandes pour permettre l'interrogation via des assistants IA compatibles MCP (VS Code Copilot, Claude Desktop, etc.).

## 🎯 Fonctionnalités

Le serveur expose les outils suivants :

| Outil | Description |
|-------|-------------|
| `get_database_schema` | Récupère le schéma complet de la base de données |
| `execute_query` | Exécute une requête SQL SELECT (lecture seule) |
| `get_table_sample` | Affiche un échantillon de données d'une table |
| `get_statistics` | Statistiques globales (clients, commandes, revenus) |
| `search_customers` | Recherche de clients par nom, email ou ville |
| `get_customer_orders` | Récupère les commandes d'un client |

## 📦 Installation

```bash
# Installer les dépendances
pip install mcp psycopg2-binary python-dotenv
```

## ⚙️ Configuration

### Variables d'environnement

```bash
POSTGRES_HOST=your-server.postgres.database.azure.com
POSTGRES_PORT=5432
POSTGRES_DATABASE=ordersdb
POSTGRES_USER=your-username
POSTGRES_PASSWORD=your-password
POSTGRES_SSL_MODE=require
```

### Configuration VS Code

Ajoutez dans votre `settings.json` VS Code ou `.vscode/mcp.json` :

```json
{
  "mcp.servers": {
    "postgres-orders": {
      "command": "python",
      "args": ["${workspaceFolder}/flask-multi-db-monorepo/mcp_postgres_server/server.py"],
      "env": {
        "POSTGRES_HOST": "your-server.postgres.database.azure.com",
        "POSTGRES_DATABASE": "ordersdb",
        "POSTGRES_USER": "your-username",
        "POSTGRES_PASSWORD": "your-password"
      }
    }
  }
}
```

### Configuration Claude Desktop

Ajoutez dans `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "postgres-orders": {
      "command": "python",
      "args": ["/path/to/mcp_postgres_server/server.py"],
      "env": {
        "POSTGRES_HOST": "your-server.postgres.database.azure.com",
        "POSTGRES_DATABASE": "ordersdb",
        "POSTGRES_USER": "your-username",
        "POSTGRES_PASSWORD": "your-password"
      }
    }
  }
}
```

## 🚀 Utilisation

### Lancement manuel (test)

```bash
cd flask-multi-db-monorepo
python -m mcp_postgres_server.server
```

### Exemples de questions à poser

Une fois le serveur configuré, vous pouvez poser des questions comme :

- "Combien de clients avons-nous ?"
- "Quelles sont les commandes en attente ?"
- "Quel est le chiffre d'affaires total ?"
- "Liste les clients de Paris"
- "Quels sont les produits les plus commandés ?"

## 🔒 Sécurité

- **Lecture seule** : Seules les requêtes SELECT sont autorisées
- **Validation** : Les requêtes sont vérifiées pour détecter les mots-clés dangereux (DROP, DELETE, etc.)
- **Limite** : Les résultats sont limités à 100 lignes par défaut

## 📊 Schéma de la base

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    customers    │       │     orders      │       │   order_items   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ customer_id (PK)│──────<│ customer_id (FK)│       │ order_item_id   │
│ first_name      │       │ order_id (PK)   │──────<│ order_id (FK)   │
│ last_name       │       │ order_date      │       │ product_sku     │
│ email           │       │ status          │       │ product_name    │
│ phone           │       │ total_amount    │       │ quantity        │
│ address         │       │ currency        │       │ unit_price      │
│ city            │       │ notes           │       └─────────────────┘
│ country         │       └─────────────────┘
└─────────────────┘
```

## 🔗 Liens

- [Documentation MCP](https://modelcontextprotocol.io/)
- [SDK Python MCP](https://github.com/modelcontextprotocol/python-sdk)
