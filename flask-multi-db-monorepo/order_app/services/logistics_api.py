"""
Logistics API - Client to communicate with Logistics App (MongoDB)
"""
import os
import requests
from typing import Dict, Any, Optional


class LogisticsAPI:
    """API client to communicate with the Logistics App."""
    
    def __init__(self):
        self.base_url = os.getenv('LOGISTICS_APP_URL', 'http://localhost:5003')
    
    def create_delivery(self, order_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new delivery for an order.
        
        Args:
            order_data: Dictionary containing:
                - order_id: PostgreSQL order UUID
                - customer_name: Full customer name
                - address: Street address
                - city: City
                - postal_code: Postal code
                - country: Country
                - notes: Optional delivery notes
        
        Returns:
            Delivery info with delivery_id and tracking_number, or None on error
        """
        try:
            response = requests.post(
                f"{self.base_url}/api/deliveries",
                json=order_data,
                timeout=10
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error creating delivery via API: {e}")
            return None
    
    def get_delivery_by_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Get delivery by order ID."""
        try:
            response = requests.get(
                f"{self.base_url}/api/deliveries/by-order/{order_id}",
                timeout=10
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            print(f"Error fetching delivery for order {order_id}: {e}")
            return None
    
    def dispatch_delivery(self, delivery_id: str, partner_id: str) -> bool:
        """Dispatch a delivery to a partner."""
        try:
            response = requests.post(
                f"{self.base_url}/api/deliveries/{delivery_id}/dispatch",
                json={'partner_id': partner_id},
                timeout=10
            )
            response.raise_for_status()
            return True
        except requests.RequestException as e:
            print(f"Error dispatching delivery: {e}")
            return False
