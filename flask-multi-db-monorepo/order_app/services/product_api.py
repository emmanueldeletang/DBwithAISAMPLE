"""
Product API - Client to fetch products from Product App (Azure SQL)
"""
import os
import requests
from typing import List, Dict, Any, Optional


class ProductAPI:
    """API client to fetch products from the Product App."""
    
    def __init__(self):
        self.base_url = os.getenv('PRODUCT_APP_URL', 'http://localhost:5001')
    
    def get_all_products(self) -> List[Dict[str, Any]]:
        """Fetch all products from Product App."""
        try:
            response = requests.get(f"{self.base_url}/api/products", timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching products from API: {e}")
            return []
    
    def get_product_by_sku(self, sku: str) -> Optional[Dict[str, Any]]:
        """Fetch a single product by SKU."""
        try:
            response = requests.get(f"{self.base_url}/api/products/{sku}", timeout=10)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching product {sku}: {e}")
            return None
    
    def search_products(self, query: str, search_type: str = 'hybrid') -> List[Dict[str, Any]]:
        """Search products."""
        try:
            response = requests.get(
                f"{self.base_url}/api/search",
                params={'q': query, 'type': search_type},
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            return data.get('results', [])
        except requests.RequestException as e:
            print(f"Error searching products: {e}")
            return []
