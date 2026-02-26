// ============================================================================
// MongoDB vCore - Logistics Database Schema
// Database: logisticsdb
// ============================================================================

// Switch to the logistics database
use('logisticsdb');

// ============================================================================
// Drop existing collections (for clean reinstall)
// ============================================================================
db.partners.drop();
db.deliveries.drop();
db.reorders.drop();

// ============================================================================
// Partners Collection
// ============================================================================
db.createCollection('partners', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['partner_id', 'name', 'contact_email', 'active'],
            properties: {
                partner_id: { bsonType: 'string' },
                name: { bsonType: 'string' },
                contact_email: { bsonType: 'string' },
                contact_phone: { bsonType: 'string' },
                service_areas: { bsonType: 'array', items: { bsonType: 'string' } },
                vehicle_types: { bsonType: 'array', items: { bsonType: 'string' } },
                active: { bsonType: 'bool' },
                created_at: { bsonType: 'date' },
                updated_at: { bsonType: 'date' }
            }
        }
    }
});

// Partners indexes
db.partners.createIndex({ partner_id: 1 }, { unique: true });
db.partners.createIndex({ name: 1 });
db.partners.createIndex({ active: 1 });
db.partners.createIndex({ service_areas: 1 });

// ============================================================================
// Deliveries Collection
// ============================================================================
db.createCollection('deliveries', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['delivery_id', 'tracking_number', 'order_id', 'customer_name', 'status'],
            properties: {
                delivery_id: { bsonType: 'string' },
                tracking_number: { bsonType: 'string' },
                order_id: { bsonType: 'string' },
                customer_name: { bsonType: 'string' },
                partner_id: { bsonType: 'string' },
                status: { 
                    enum: ['pending', 'picked_up', 'in_transit', 'out_for_delivery', 'delivered', 'failed', 'returned']
                },
                status_text: { bsonType: 'string' },
                address: {
                    bsonType: 'object',
                    properties: {
                        street: { bsonType: 'string' },
                        city: { bsonType: 'string' },
                        postal_code: { bsonType: 'string' },
                        country: { bsonType: 'string' }
                    }
                },
                notes: { bsonType: 'string' },
                eta: { bsonType: 'date' },
                events: {
                    bsonType: 'array',
                    items: {
                        bsonType: 'object',
                        properties: {
                            timestamp: { bsonType: 'date' },
                            status: { bsonType: 'string' },
                            description: { bsonType: 'string' },
                            location: { bsonType: 'string' }
                        }
                    }
                },
                content_embedding: {
                    bsonType: 'array',
                    items: { bsonType: 'double' }
                },
                created_at: { bsonType: 'date' },
                updated_at: { bsonType: 'date' },
                last_update: { bsonType: 'date' }
            }
        }
    }
});

// Deliveries indexes
db.deliveries.createIndex({ delivery_id: 1 }, { unique: true });
db.deliveries.createIndex({ tracking_number: 1 }, { unique: true });
db.deliveries.createIndex({ order_id: 1 });
db.deliveries.createIndex({ partner_id: 1 });
db.deliveries.createIndex({ status: 1 });
db.deliveries.createIndex({ created_at: -1 });
db.deliveries.createIndex({ 'address.city': 1 });

// Full-text search index
db.deliveries.createIndex(
    { 
        customer_name: 'text', 
        status_text: 'text', 
        notes: 'text',
        'address.street': 'text',
        'address.city': 'text'
    },
    { 
        name: 'deliveries_text_idx',
        weights: {
            customer_name: 10,
            'address.city': 5,
            status_text: 3,
            notes: 1
        }
    }
);

// Vector search index for Cosmos DB for MongoDB vCore
// Note: This uses the cosmosSearch index type
db.runCommand({
    createIndexes: 'deliveries',
    indexes: [
        {
            name: 'vector_index',
            key: { content_embedding: 'cosmosSearch' },
            cosmosSearchOptions: {
                kind: 'vector-diskann',    // or 'vector-hnsw'
                similarity: 'COS',          // Cosine similarity
                dimensions: 3072            // text-embedding-3-large
            }
        }
    ]
});

// ============================================================================
// Reorders Collection (populated by InventoryAgent)
// ============================================================================
db.createCollection('reorders', {
    validator: {
        $jsonSchema: {
            bsonType: 'object',
            required: ['reorder_id', 'sku', 'product_name', 'current_stock', 'reorder_quantity', 'status'],
            properties: {
                reorder_id: { bsonType: 'string' },
                sku: { bsonType: 'string' },
                product_name: { bsonType: 'string' },
                category: { bsonType: 'string' },
                current_stock: { bsonType: 'int' },
                reorder_quantity: { bsonType: 'int' },
                estimated_cost: { bsonType: 'double' },
                currency: { bsonType: 'string' },
                status: {
                    enum: ['pending', 'approved', 'ordered', 'received', 'cancelled']
                },
                created_at: { bsonType: 'date' },
                created_by: { bsonType: 'string' },
                notes: { bsonType: 'string' }
            }
        }
    }
});

// Reorders indexes
db.reorders.createIndex({ reorder_id: 1 }, { unique: true });
db.reorders.createIndex({ sku: 1 });
db.reorders.createIndex({ status: 1 });
db.reorders.createIndex({ created_at: -1 });

// ============================================================================
// Seed Data - Partners
// ============================================================================
db.partners.insertMany([
    {
        partner_id: 'PART001',
        name: 'SpeedyExpress',
        contact_email: 'contact@speedyexpress.fr',
        contact_phone: '+33 1 23 45 67 89',
        service_areas: ['Paris', 'Lyon', 'Marseille', 'Bordeaux', 'Toulouse'],
        vehicle_types: ['Van', 'Truck', 'Bike'],
        active: true,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        partner_id: 'PART002',
        name: 'EcoLivraison',
        contact_email: 'hello@ecolivraison.fr',
        contact_phone: '+33 1 34 56 78 90',
        service_areas: ['Paris', 'Lille', 'Nantes', 'Nice'],
        vehicle_types: ['Electric Van', 'Cargo Bike'],
        active: true,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        partner_id: 'PART003',
        name: 'FlashDelivery',
        contact_email: 'pro@flashdelivery.fr',
        contact_phone: '+33 1 45 67 89 01',
        service_areas: ['Lyon', 'Grenoble', 'Saint-Étienne'],
        vehicle_types: ['Van', 'Scooter'],
        active: true,
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        partner_id: 'PART004',
        name: 'NightOwl Logistics',
        contact_email: 'support@nightowl.fr',
        contact_phone: '+33 1 56 78 90 12',
        service_areas: ['Paris', 'Lyon', 'Marseille'],
        vehicle_types: ['Truck', 'Van'],
        active: false,
        created_at: new Date(),
        updated_at: new Date()
    }
]);

// ============================================================================
// Seed Data - Deliveries
// ============================================================================
const now = new Date();
const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
const twoDaysAgo = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);

db.deliveries.insertMany([
    {
        delivery_id: 'DEL001',
        tracking_number: 'TRK7A8B9C0D1E',
        order_id: 'ORD-2024-001',
        customer_name: 'Jean Dupont',
        partner_id: 'PART001',
        status: 'in_transit',
        status_text: 'Package is on the way to destination',
        address: {
            street: '15 Rue de la Paix',
            city: 'Paris',
            postal_code: '75001',
            country: 'France'
        },
        notes: 'Leave at door if not home',
        eta: new Date(now.getTime() + 4 * 60 * 60 * 1000),
        events: [
            { timestamp: twoDaysAgo, status: 'pending', description: 'Order received', location: '' },
            { timestamp: yesterday, status: 'picked_up', description: 'Package picked up from warehouse', location: 'Paris Hub' },
            { timestamp: now, status: 'in_transit', description: 'Package in transit', location: 'Paris Distribution Center' }
        ],
        created_at: twoDaysAgo,
        updated_at: now,
        last_update: now
    },
    {
        delivery_id: 'DEL002',
        tracking_number: 'TRK2F3G4H5I6J',
        order_id: 'ORD-2024-002',
        customer_name: 'Marie Martin',
        partner_id: 'PART002',
        status: 'out_for_delivery',
        status_text: 'Package is out for delivery',
        address: {
            street: '28 Avenue des Champs-Élysées',
            city: 'Paris',
            postal_code: '75008',
            country: 'France'
        },
        notes: 'Call before delivery',
        eta: new Date(now.getTime() + 2 * 60 * 60 * 1000),
        events: [
            { timestamp: twoDaysAgo, status: 'pending', description: 'Order received', location: '' },
            { timestamp: yesterday, status: 'picked_up', description: 'Package picked up', location: 'Paris Hub' },
            { timestamp: yesterday, status: 'in_transit', description: 'Package in transit', location: '' },
            { timestamp: now, status: 'out_for_delivery', description: 'Out for delivery', location: 'Paris 8ème' }
        ],
        created_at: twoDaysAgo,
        updated_at: now,
        last_update: now
    },
    {
        delivery_id: 'DEL003',
        tracking_number: 'TRK3K4L5M6N7O',
        order_id: 'ORD-2024-003',
        customer_name: 'Pierre Bernard',
        partner_id: 'PART003',
        status: 'delivered',
        status_text: 'Package delivered successfully',
        address: {
            street: '42 Rue de la République',
            city: 'Lyon',
            postal_code: '69001',
            country: 'France'
        },
        notes: '',
        events: [
            { timestamp: twoDaysAgo, status: 'pending', description: 'Order received', location: '' },
            { timestamp: twoDaysAgo, status: 'picked_up', description: 'Package picked up', location: 'Lyon Hub' },
            { timestamp: yesterday, status: 'in_transit', description: 'Package in transit', location: '' },
            { timestamp: yesterday, status: 'out_for_delivery', description: 'Out for delivery', location: 'Lyon 1er' },
            { timestamp: now, status: 'delivered', description: 'Delivered to recipient', location: 'Lyon 1er' }
        ],
        created_at: twoDaysAgo,
        updated_at: now,
        last_update: now
    },
    {
        delivery_id: 'DEL004',
        tracking_number: 'TRK4P5Q6R7S8T',
        order_id: 'ORD-2024-004',
        customer_name: 'Sophie Petit',
        partner_id: null,
        status: 'pending',
        status_text: 'Awaiting pickup',
        address: {
            street: '7 Place Bellecour',
            city: 'Lyon',
            postal_code: '69002',
            country: 'France'
        },
        notes: 'Fragile items - handle with care',
        events: [
            { timestamp: now, status: 'pending', description: 'Order received, awaiting partner assignment', location: '' }
        ],
        created_at: now,
        updated_at: now,
        last_update: now
    },
    {
        delivery_id: 'DEL005',
        tracking_number: 'TRK5U6V7W8X9Y',
        order_id: 'ORD-2024-005',
        customer_name: 'Lucas Robert',
        partner_id: 'PART001',
        status: 'failed',
        status_text: 'Delivery attempt failed - recipient not available',
        address: {
            street: '33 Quai des Belges',
            city: 'Marseille',
            postal_code: '13001',
            country: 'France'
        },
        notes: 'Second attempt scheduled for tomorrow',
        events: [
            { timestamp: twoDaysAgo, status: 'pending', description: 'Order received', location: '' },
            { timestamp: twoDaysAgo, status: 'picked_up', description: 'Package picked up', location: 'Marseille Hub' },
            { timestamp: yesterday, status: 'in_transit', description: 'Package in transit', location: '' },
            { timestamp: yesterday, status: 'out_for_delivery', description: 'Out for delivery', location: 'Marseille Centre' },
            { timestamp: now, status: 'failed', description: 'Delivery failed - no one home', location: 'Marseille Centre' }
        ],
        created_at: twoDaysAgo,
        updated_at: now,
        last_update: now
    }
]);

// ============================================================================
// Verification
// ============================================================================
print('MongoDB Logistics schema created successfully!');
print('Partners inserted: ' + db.partners.countDocuments());
print('Deliveries inserted: ' + db.deliveries.countDocuments());
print('');
print('Indexes created:');
db.partners.getIndexes().forEach(idx => print('  partners.' + idx.name));
db.deliveries.getIndexes().forEach(idx => print('  deliveries.' + idx.name));
