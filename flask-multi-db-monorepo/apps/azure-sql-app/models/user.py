"""
Product model for Azure SQL (data class representation)
Used with mssql-python driver - no ORM, raw SQL queries
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Product:
    """Product data class representing a row in the products table."""
    
    sku: str
    name: str
    price: float
    currency: str = 'EUR'
    description: Optional[str] = None
    tags: Optional[str] = None
    stock: int = 0
    category: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            'sku': self.sku,
            'name': self.name,
            'description': self.description,
            'price': self.price,
            'currency': self.currency,
            'tags': self.tags,
            'stock': self.stock,
            'category': self.category,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_row(cls, row: tuple, columns: list) -> 'Product':
        """Create Product from database row."""
        data = dict(zip(columns, row))
        return cls(
            sku=data.get('sku'),
            name=data.get('name'),
            description=data.get('description'),
            price=float(data.get('price', 0)),
            currency=data.get('currency', 'EUR'),
            tags=data.get('tags'),
            stock=int(data.get('stock', 0)),
            category=data.get('category'),
            created_at=data.get('created_at')
        )
    
    def __repr__(self):
        return f"<Product(sku={self.sku}, name={self.name})>"