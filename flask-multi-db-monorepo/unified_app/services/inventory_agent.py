"""
Inventory Agent - Checks product stock levels and creates reorders in MongoDB.

Scans all products in Azure SQL. For any product with stock < 10, generates
a reorder document and inserts it into the `reorders` collection in
Cosmos DB for MongoDB (logisticsdb).

Can be launched:
  - As a CLI command:   python -m unified_app.services.inventory_agent
  - Via Flask route:     POST /inventory/check
  - On a schedule (cron / Azure Function timer trigger)
"""
import sys
import os
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from pymongo import MongoClient
from shared.config import azure_sql_config, mongodb_config

# ── Tunables ─────────────────────────────────────────────────────────
REORDER_THRESHOLD = 10          # reorder when stock < this value
REORDER_QUANTITY  = 50          # how many units to reorder each time
COLLECTION_NAME   = "reorders"  # MongoDB collection for reorder logs
# ─────────────────────────────────────────────────────────────────────


class InventoryAgent:
    """Agent that monitors product stock and creates reorder requests."""

    def __init__(self, threshold: int = REORDER_THRESHOLD,
                 reorder_qty: int = REORDER_QUANTITY):
        self.threshold = threshold
        self.reorder_qty = reorder_qty
        self._mongo_client = None
        self._mongo_db = None

    # ── MongoDB connection ───────────────────────────────────────────
    def _get_mongo_db(self):
        if self._mongo_client is None:
            self._mongo_client = MongoClient(mongodb_config.connection_string)
            self._mongo_db = self._mongo_client[mongodb_config.database]
        return self._mongo_db

    # ── Read products from Azure SQL ─────────────────────────────────
    def get_low_stock_products(self) -> List[Dict[str, Any]]:
        """Return all products whose stock is below the threshold."""
        query = """
            SELECT sku, name, stock, category, price, currency
            FROM products
            WHERE stock < ?
            ORDER BY stock ASC
        """
        results = []
        try:
            with azure_sql_config.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (self.threshold,))
                columns = [col[0] for col in cursor.description]
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
        except Exception as e:
            print(f"[InventoryAgent] Error querying products: {e}")
        return results

    def get_all_stock_summary(self) -> Dict[str, Any]:
        """Return a quick stock summary across all products."""
        query = """
            SELECT
                COUNT(*)                          AS total_products,
                SUM(CASE WHEN stock < ? THEN 1 ELSE 0 END) AS low_stock_count,
                SUM(CASE WHEN stock = 0 THEN 1 ELSE 0 END) AS out_of_stock_count,
                MIN(stock)                        AS min_stock,
                AVG(stock)                        AS avg_stock
            FROM products
        """
        try:
            with azure_sql_config.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, (self.threshold,))
                row = cursor.fetchone()
                return {
                    'total_products': row[0],
                    'low_stock_count': row[1],
                    'out_of_stock_count': row[2],
                    'min_stock': row[3],
                    'avg_stock': float(row[4]) if row[4] else 0,
                    'threshold': self.threshold
                }
        except Exception as e:
            print(f"[InventoryAgent] Error getting stock summary: {e}")
            return {}

    # ── Create reorder documents in MongoDB ──────────────────────────
    def _build_reorder_doc(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Build a reorder document for a single low-stock product."""
        return {
            'reorder_id': str(uuid.uuid4())[:8].upper(),
            'sku': product['sku'],
            'product_name': product['name'],
            'category': product.get('category', ''),
            'current_stock': product['stock'],
            'reorder_quantity': self.reorder_qty,
            'estimated_cost': round(float(product.get('price', 0)) * self.reorder_qty, 2),
            'currency': product.get('currency', 'EUR'),
            'status': 'pending',
            'created_at': datetime.now(timezone.utc),
            'created_by': 'inventory-agent',
            'notes': f"Auto-reorder: stock ({product['stock']}) below threshold ({self.threshold})"
        }

    def _get_pending_skus(self) -> set:
        """Return the set of SKUs that already have a pending reorder."""
        db = self._get_mongo_db()
        collection = db[COLLECTION_NAME]
        return {
            doc['sku']
            for doc in collection.find({'status': 'pending'}, {'sku': 1})
        }

    def create_reorders(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Insert reorder docs into MongoDB and return them.
        Skips products that already have a pending reorder."""
        if not products:
            return []

        db = self._get_mongo_db()
        collection = db[COLLECTION_NAME]

        # Filter out products that already have a pending reorder
        pending_skus = self._get_pending_skus()
        new_products = [p for p in products if p['sku'] not in pending_skus]

        if not new_products:
            return []

        docs = [self._build_reorder_doc(p) for p in new_products]
        collection.insert_many(docs)

        # Convert datetimes for JSON serialisation
        for d in docs:
            d.pop('_id', None)
            if isinstance(d.get('created_at'), datetime):
                d['created_at'] = d['created_at'].isoformat()

        return docs

    # ── Get existing reorders from MongoDB ───────────────────────────
    def get_reorders(self, status: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch reorder documents from MongoDB."""
        db = self._get_mongo_db()
        collection = db[COLLECTION_NAME]

        query = {}
        if status:
            query['status'] = status

        results = []
        for doc in collection.find(query).sort('created_at', -1).limit(limit):
            doc['_id'] = str(doc['_id'])
            if isinstance(doc.get('created_at'), datetime):
                doc['created_at'] = doc['created_at'].isoformat()
            results.append(doc)
        return results

    def count_reorders(self, status: str = None) -> int:
        """Count reorder documents."""
        db = self._get_mongo_db()
        query = {'status': status} if status else {}
        return db[COLLECTION_NAME].count_documents(query)

    # ── Fulfill a reorder ─────────────────────────────────────────────
    def fulfill_reorder(self, reorder_id: str) -> Dict[str, Any]:
        """
        Mark a reorder as 'received' and add the reorder quantity back
        to the product stock in Azure SQL.
        Returns the updated reorder doc or raises an exception.
        """
        db = self._get_mongo_db()
        collection = db[COLLECTION_NAME]

        # Find the reorder
        reorder = collection.find_one({'reorder_id': reorder_id})
        if not reorder:
            raise ValueError(f"Reorder {reorder_id} not found")
        if reorder.get('status') != 'pending':
            raise ValueError(f"Reorder {reorder_id} is already '{reorder.get('status')}', cannot fulfill")

        sku = reorder['sku']
        qty = reorder['reorder_quantity']

        # Increase stock in Azure SQL
        try:
            with azure_sql_config.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE products SET stock = stock + ? WHERE sku = ?",
                    (qty, sku)
                )
                conn.commit()
        except Exception as e:
            raise RuntimeError(f"Failed to update stock for {sku}: {e}")

        # Mark reorder as received in MongoDB
        collection.update_one(
            {'reorder_id': reorder_id},
            {'$set': {
                'status': 'received',
                'received_at': datetime.now(timezone.utc),
                'received_by': 'inventory-agent'
            }}
        )

        return {
            'reorder_id': reorder_id,
            'sku': sku,
            'quantity_added': qty,
            'new_status': 'received'
        }

    # ── Cancel and delete a reorder ───────────────────────────────────
    def cancel_reorder(self, reorder_id: str) -> Dict[str, Any]:
        """
        Cancel a pending reorder and delete it from MongoDB.
        Returns info about the cancelled reorder or raises an exception.
        """
        db = self._get_mongo_db()
        collection = db[COLLECTION_NAME]

        # Find the reorder
        reorder = collection.find_one({'reorder_id': reorder_id})
        if not reorder:
            raise ValueError(f"Reorder {reorder_id} not found")
        if reorder.get('status') != 'pending':
            raise ValueError(f"Reorder {reorder_id} is '{reorder.get('status')}', only pending reorders can be cancelled")

        sku = reorder['sku']
        product_name = reorder.get('product_name', '')

        # Delete the reorder document from MongoDB
        collection.delete_one({'reorder_id': reorder_id})

        return {
            'reorder_id': reorder_id,
            'sku': sku,
            'product_name': product_name,
            'status': 'deleted'
        }

    # ── Main run method ──────────────────────────────────────────────
    def run(self) -> Dict[str, Any]:
        """
        Execute a full inventory check:
          1. Query Azure SQL for products with stock < threshold
          2. For each, create a reorder document in MongoDB
          3. Return a summary
        """
        print(f"[InventoryAgent] Checking stock levels (threshold={self.threshold})...")

        summary = self.get_all_stock_summary()
        low_stock = self.get_low_stock_products()

        print(f"[InventoryAgent] Found {len(low_stock)} product(s) below threshold.")

        reorders = []
        if low_stock:
            reorders = self.create_reorders(low_stock)
            print(f"[InventoryAgent] Created {len(reorders)} reorder(s) in MongoDB.")

        result = {
            'run_at': datetime.now(timezone.utc).isoformat(),
            'summary': summary,
            'low_stock_products': low_stock,
            'reorders_created': reorders,
            'reorders_count': len(reorders)
        }
        return result


# ── CLI entry-point ──────────────────────────────────────────────────
if __name__ == '__main__':
    import json

    agent = InventoryAgent()
    result = agent.run()

    print("\n" + "=" * 60)
    print("  Inventory Agent Report")
    print("=" * 60)

    s = result.get('summary', {})
    print(f"  Total products:     {s.get('total_products', '?')}")
    print(f"  Low stock (<{agent.threshold}):   {s.get('low_stock_count', '?')}")
    print(f"  Out of stock (=0):  {s.get('out_of_stock_count', '?')}")
    print(f"  Reorders created:   {result['reorders_count']}")

    if result['reorders_created']:
        print("\n  Reorders:")
        for r in result['reorders_created']:
            print(f"    [{r['reorder_id']}] {r['product_name']} "
                  f"(stock={r['current_stock']}) → +{r['reorder_quantity']} units")

    print("=" * 60)
