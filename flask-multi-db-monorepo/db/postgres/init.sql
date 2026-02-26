-- ============================================================================
-- PostgreSQL Database - Customers & Orders Schema
-- Database: ordersdb
-- ============================================================================

-- Enable required extensions (some may not be available on Azure)
-- uuid-ossp is optional since PostgreSQL 13+ has gen_random_uuid() built-in
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- Optional
-- CREATE EXTENSION IF NOT EXISTS "vector";     -- Requires Azure PostgreSQL with vector extension

-- ============================================================================
-- Customers Table
-- ============================================================================
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    customer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    phone VARCHAR(50),
    address TEXT,
    city VARCHAR(100),
    country VARCHAR(100),
    
    -- Vector column for name embeddings (for semantic search)
    -- Uncomment if vector extension is available:
    -- name_embedding vector(3072),
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Orders Table
-- ============================================================================
CREATE TABLE orders (
    order_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers(customer_id) ON DELETE CASCADE,
    order_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'confirmed', 'processing', 'shipped', 'delivered', 'cancelled')),
    total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0,
    currency VARCHAR(3) DEFAULT 'EUR',
    notes TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Order Items Table
-- ============================================================================
CREATE TABLE order_items (
    order_item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id UUID NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    product_sku VARCHAR(50) NOT NULL, -- References product in Azure SQL
    product_name VARCHAR(200) NOT NULL,
    quantity INT NOT NULL CHECK (quantity > 0),
    unit_price DECIMAL(10, 2) NOT NULL,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Customer indexes
CREATE INDEX idx_customers_email ON customers(email);
CREATE INDEX idx_customers_city ON customers(city);
CREATE INDEX idx_customers_country ON customers(country);

-- Trigram indexes for fuzzy text search
CREATE INDEX idx_customers_first_name_trgm ON customers USING GIN (first_name gin_trgm_ops);
CREATE INDEX idx_customers_last_name_trgm ON customers USING GIN (last_name gin_trgm_ops);
CREATE INDEX idx_customers_email_trgm ON customers USING GIN (email gin_trgm_ops);

-- Vector index for similarity search (using IVFFlat or HNSW)
CREATE INDEX idx_customers_name_embedding ON customers USING ivfflat (name_embedding vector_cosine_ops) WITH (lists = 100);
-- Alternative: HNSW index (better accuracy, more memory)
-- CREATE INDEX idx_customers_name_embedding_hnsw ON customers USING hnsw (name_embedding vector_cosine_ops);

-- Order indexes
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_date ON orders(order_date DESC);

-- Order items indexes
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_sku ON order_items(product_sku);

-- ============================================================================
-- Functions
-- ============================================================================

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_orders_updated_at
    BEFORE UPDATE ON orders
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Seed Data
-- ============================================================================

-- Insert sample customers
INSERT INTO customers (first_name, last_name, email, phone, address, city, country) VALUES
('Jean', 'Dupont', 'jean.dupont@email.fr', '+33 6 12 34 56 78', '15 Rue de la Paix', 'Paris', 'France'),
('Marie', 'Martin', 'marie.martin@email.fr', '+33 6 23 45 67 89', '28 Avenue des Champs-Élysées', 'Paris', 'France'),
('Pierre', 'Bernard', 'pierre.bernard@email.fr', '+33 6 34 56 78 90', '42 Rue de la République', 'Lyon', 'France'),
('Sophie', 'Petit', 'sophie.petit@email.fr', '+33 6 45 67 89 01', '7 Place Bellecour', 'Lyon', 'France'),
('Lucas', 'Robert', 'lucas.robert@email.fr', '+33 6 56 78 90 12', '33 Quai des Belges', 'Marseille', 'France'),
('Emma', 'Richard', 'emma.richard@email.fr', '+33 6 67 89 01 23', '12 Rue Sainte-Catherine', 'Bordeaux', 'France'),
('Louis', 'Durand', 'louis.durand@email.fr', '+33 6 78 90 12 34', '56 Place du Capitole', 'Toulouse', 'France'),
('Léa', 'Leroy', 'lea.leroy@email.fr', '+33 6 89 01 23 45', '89 Rue de la Liberté', 'Lille', 'France'),
('Hugo', 'Moreau', 'hugo.moreau@email.fr', '+33 6 90 12 34 56', '23 Avenue Jean Jaurès', 'Nantes', 'France'),
('Chloé', 'Simon', 'chloe.simon@email.fr', '+33 6 01 23 45 67', '67 Rue du Vieux Port', 'Nice', 'France');

-- Insert sample orders
INSERT INTO orders (customer_id, status, total_amount, currency, notes)
SELECT customer_id, 'confirmed', 1549.98, 'EUR', 'Priority shipping requested'
FROM customers WHERE email = 'jean.dupont@email.fr';

INSERT INTO orders (customer_id, status, total_amount, currency)
SELECT customer_id, 'processing', 449.98, 'EUR'
FROM customers WHERE email = 'marie.martin@email.fr';

INSERT INTO orders (customer_id, status, total_amount, currency)
SELECT customer_id, 'shipped', 2399.98, 'EUR'
FROM customers WHERE email = 'pierre.bernard@email.fr';

INSERT INTO orders (customer_id, status, total_amount, currency)
SELECT customer_id, 'delivered', 179.99, 'EUR'
FROM customers WHERE email = 'sophie.petit@email.fr';

INSERT INTO orders (customer_id, status, total_amount, currency)
SELECT customer_id, 'pending', 629.98, 'EUR'
FROM customers WHERE email = 'lucas.robert@email.fr';

-- Insert order items
INSERT INTO order_items (order_id, product_sku, product_name, quantity, unit_price)
SELECT order_id, 'LAPTOP-PRO-001', 'ProBook Laptop 15"', 1, 1299.99
FROM orders o JOIN customers c ON o.customer_id = c.customer_id
WHERE c.email = 'jean.dupont@email.fr';

INSERT INTO order_items (order_id, product_sku, product_name, quantity, unit_price)
SELECT order_id, 'DOCK-USB-001', 'UniversalDock Pro', 1, 249.99
FROM orders o JOIN customers c ON o.customer_id = c.customer_id
WHERE c.email = 'jean.dupont@email.fr';

INSERT INTO order_items (order_id, product_sku, product_name, quantity, unit_price)
SELECT order_id, 'HEADPHONES-WL-001', 'SoundWave Pro Wireless', 1, 299.99
FROM orders o JOIN customers c ON o.customer_id = c.customer_id
WHERE c.email = 'marie.martin@email.fr';

INSERT INTO order_items (order_id, product_sku, product_name, quantity, unit_price)
SELECT order_id, 'HEADPHONES-GAMING-001', 'ProGamer Headset 7.1', 1, 149.99
FROM orders o JOIN customers c ON o.customer_id = c.customer_id
WHERE c.email = 'marie.martin@email.fr';

-- ============================================================================
-- Views for common queries
-- ============================================================================

CREATE OR REPLACE VIEW v_order_summary AS
SELECT 
    o.order_id,
    o.order_date,
    o.status,
    o.total_amount,
    o.currency,
    c.first_name,
    c.last_name,
    c.email,
    c.city,
    COUNT(oi.order_item_id) as item_count
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
LEFT JOIN order_items oi ON o.order_id = oi.order_id
GROUP BY o.order_id, o.order_date, o.status, o.total_amount, o.currency,
         c.first_name, c.last_name, c.email, c.city;

-- ============================================================================
-- Application Users Table
-- ============================================================================
DROP TABLE IF EXISTS app_users CASCADE;

CREATE TABLE app_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Done
-- ============================================================================
SELECT 'PostgreSQL Orders schema created successfully!' as message;
SELECT 'Customers inserted: ' || COUNT(*) as info FROM customers;
SELECT 'Orders inserted: ' || COUNT(*) as info FROM orders;
