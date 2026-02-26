from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from shared.database.postgresql import Base

class Product(Base):
    __tablename__ = 'products'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    price = Column(Integer, nullable=False)
    currency = Column(String(3), nullable=False)
    tags = Column(String)  # Comma-separated tags
    stock = Column(Integer, default=0)
    created_at = Column(String)  # Use a proper date type in production
    customer_id = Column(Integer, ForeignKey('customers.id'))

    customer = relationship("Customer", back_populates="products")

class Customer(Base):
    __tablename__ = 'customers'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    products = relationship("Product", back_populates="customer")