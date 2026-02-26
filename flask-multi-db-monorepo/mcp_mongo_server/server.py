"""
MCP (Model Context Protocol) Server for MongoDB
Provides tools for querying the Logistics database via natural language
and generating statistics with aggregation pipelines.
"""
import os
import sys
import json
import asyncio
from datetime import datetime
from typing import Any, Optional, List, Dict
from dotenv import load_dotenv

# MongoDB imports
try:
    from pymongo import MongoClient
    from bson import ObjectId, json_util
except ImportError:
    print("pymongo not installed. Install with: pip install pymongo", file=sys.stderr)
    sys.exit(1)

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent
except ImportError:
    print("MCP SDK not installed. Install with: pip install mcp", file=sys.stderr)
    sys.exit(1)

load_dotenv()


# ============================================================================
# Database Configuration
# ============================================================================

def get_db_connection():
    """Create MongoDB connection."""
    host = os.getenv('MONGODB_HOST', 'localhost')
    user = os.getenv('MONGODB_USER', '')
    password = os.getenv('MONGODB_PASSWORD', '')
    database = os.getenv('MONGODB_DATABASE', 'logisticsdb')
    
    if user and password:
        connection_string = f"mongodb+srv://{user}:{password}@{host}/?tls=true&authMechanism=SCRAM-SHA-256&retrywrites=false&maxIdleTimeMS=120000"
    else:
        connection_string = f"mongodb://{host}:27017/"
    
    client = MongoClient(connection_string)
    return client[database]


def serialize_doc(doc: dict) -> dict:
    """Serialize MongoDB document for JSON output."""
    return json.loads(json_util.dumps(doc))


# ============================================================================
# Database Schema Information
# ============================================================================

DATABASE_SCHEMA = """
## Database: logisticsdb (MongoDB / Cosmos DB vCore)

### Collections:

**deliveries**
- delivery_id (string) - Unique delivery identifier
- tracking_number (string) - Tracking number (TRK...)
- order_id (string) - Reference to PostgreSQL order
- customer_name (string) - Full customer name
- partner_id (string) - Delivery partner ID
- status (string): 'pending', 'picked_up', 'in_transit', 'out_for_delivery', 'delivered', 'failed'
- status_text (string) - Human-readable status
- address (object):
  - street (string)
  - city (string)
  - postal_code (string)
  - country (string)
- notes (string) - Delivery notes
- eta (datetime) - Estimated time of arrival
- events (array of objects):
  - timestamp (datetime)
  - status (string)
  - description (string)
  - location (string)
- created_at (datetime)
- updated_at (datetime)

**partners**
- partner_id (string) - Unique partner identifier
- name (string) - Partner company name
- contact_email (string)
- contact_phone (string)
- service_areas (array of strings) - Cities served
- vehicle_types (array of strings) - Vehicle fleet types
- active (boolean)
- created_at (datetime)
- updated_at (datetime)

### Common Aggregations:
- Deliveries by status
- Deliveries by city
- Deliveries by partner
- Average delivery time
- Partner performance metrics
"""


# ============================================================================
# Predefined Aggregation Pipelines
# ============================================================================

AGGREGATION_PIPELINES = {
    "deliveries_by_status": {
        "description": "Count deliveries grouped by status",
        "collection": "deliveries",
        "pipeline": [
            {"$group": {"_id": "$status", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
    },
    "deliveries_by_city": {
        "description": "Count deliveries grouped by destination city",
        "collection": "deliveries",
        "pipeline": [
            {"$group": {"_id": "$address.city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
    },
    "deliveries_by_partner": {
        "description": "Count deliveries grouped by delivery partner",
        "collection": "deliveries",
        "pipeline": [
            {"$match": {"partner_id": {"$ne": None}}},
            {"$group": {"_id": "$partner_id", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
    },
    "pending_deliveries_by_city": {
        "description": "Count pending deliveries grouped by city",
        "collection": "deliveries",
        "pipeline": [
            {"$match": {"status": "pending"}},
            {"$group": {"_id": "$address.city", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
    },
    "partner_performance": {
        "description": "Partner performance: deliveries by status for each partner",
        "collection": "deliveries",
        "pipeline": [
            {"$match": {"partner_id": {"$ne": None}}},
            {"$group": {
                "_id": {"partner": "$partner_id", "status": "$status"},
                "count": {"$sum": 1}
            }},
            {"$group": {
                "_id": "$_id.partner",
                "statuses": {"$push": {"status": "$_id.status", "count": "$count"}},
                "total": {"$sum": "$count"}
            }},
            {"$sort": {"total": -1}}
        ]
    },
    "active_partners_summary": {
        "description": "Summary of active partners with their service areas",
        "collection": "partners",
        "pipeline": [
            {"$match": {"active": True}},
            {"$project": {
                "name": 1,
                "service_areas": 1,
                "vehicle_types": 1,
                "areas_count": {"$size": "$service_areas"}
            }},
            {"$sort": {"areas_count": -1}}
        ]
    },
    "deliveries_timeline": {
        "description": "Deliveries created per day (last 30 days)",
        "collection": "deliveries",
        "pipeline": [
            {"$project": {
                "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}}
            }},
            {"$group": {"_id": "$date", "count": {"$sum": 1}}},
            {"$sort": {"_id": -1}},
            {"$limit": 30}
        ]
    },
    "delivery_notes_analysis": {
        "description": "Most common delivery notes",
        "collection": "deliveries",
        "pipeline": [
            {"$match": {"notes": {"$ne": ""}}},
            {"$group": {"_id": "$notes", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
    }
}


# ============================================================================
# MCP Server
# ============================================================================

server = Server("mongodb-logistics-mcp")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="get_database_schema",
            description="Get the MongoDB database schema information for the Logistics database. Use this to understand the collections and fields available.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="find_documents",
            description="Find documents in a MongoDB collection using a query filter. Returns matching documents.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name",
                        "enum": ["deliveries", "partners"]
                    },
                    "filter": {
                        "type": "object",
                        "description": "MongoDB query filter (e.g., {\"status\": \"pending\"})"
                    },
                    "projection": {
                        "type": "object",
                        "description": "Fields to include/exclude (e.g., {\"_id\": 0, \"customer_name\": 1})"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum documents to return (default: 20)",
                        "default": 20
                    },
                    "sort": {
                        "type": "object",
                        "description": "Sort order (e.g., {\"created_at\": -1} for newest first)"
                    }
                },
                "required": ["collection"]
            }
        ),
        Tool(
            name="run_aggregation",
            description="Run a MongoDB aggregation pipeline on a collection. For complex analytics and statistics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name",
                        "enum": ["deliveries", "partners"]
                    },
                    "pipeline": {
                        "type": "array",
                        "description": "Aggregation pipeline stages (array of stage objects)",
                        "items": {"type": "object"}
                    }
                },
                "required": ["collection", "pipeline"]
            }
        ),
        Tool(
            name="list_predefined_stats",
            description="List all predefined statistical aggregations available. Use this to discover what statistics can be generated.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="run_predefined_stats",
            description="Run a predefined statistical aggregation by name. Easier than writing custom pipelines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "stat_name": {
                        "type": "string",
                        "description": "Name of the predefined statistic",
                        "enum": list(AGGREGATION_PIPELINES.keys())
                    }
                },
                "required": ["stat_name"]
            }
        ),
        Tool(
            name="get_collection_sample",
            description="Get sample documents from a collection to understand the data structure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection": {
                        "type": "string",
                        "description": "Collection name",
                        "enum": ["deliveries", "partners"]
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of sample documents (default: 3)",
                        "default": 3
                    }
                },
                "required": ["collection"]
            }
        ),
        Tool(
            name="get_dashboard_stats",
            description="Get a comprehensive dashboard with key statistics: counts, status breakdown, partner activity.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": []
            }
        ),
        Tool(
            name="search_deliveries",
            description="Search deliveries by customer name, tracking number, or city using text search.",
            inputSchema={
                "type": "object",
                "properties": {
                    "search_term": {
                        "type": "string",
                        "description": "Search term to find in deliveries"
                    }
                },
                "required": ["search_term"]
            }
        ),
        Tool(
            name="track_delivery",
            description="Get detailed tracking information for a delivery by tracking number or delivery ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "Tracking number (TRK...) or delivery ID"
                    }
                },
                "required": ["identifier"]
            }
        ),
        Tool(
            name="get_partner_details",
            description="Get details about a delivery partner including their service areas and active deliveries.",
            inputSchema={
                "type": "object",
                "properties": {
                    "partner_id": {
                        "type": "string",
                        "description": "Partner ID (e.g., PART001)"
                    }
                },
                "required": ["partner_id"]
            }
        )
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    
    try:
        db = get_db_connection()
    except Exception as e:
        return [TextContent(type="text", text=f"Error connecting to MongoDB: {str(e)}")]
    
    # ========================================================================
    # get_database_schema
    # ========================================================================
    if name == "get_database_schema":
        return [TextContent(type="text", text=DATABASE_SCHEMA)]
    
    # ========================================================================
    # find_documents
    # ========================================================================
    elif name == "find_documents":
        collection_name = arguments.get("collection")
        query_filter = arguments.get("filter", {})
        projection = arguments.get("projection")
        limit = arguments.get("limit", 20)
        sort = arguments.get("sort")
        
        try:
            collection = db[collection_name]
            cursor = collection.find(query_filter, projection)
            
            if sort:
                cursor = cursor.sort(list(sort.items()))
            
            cursor = cursor.limit(limit)
            
            docs = [serialize_doc(doc) for doc in cursor]
            
            result = {
                "collection": collection_name,
                "filter": query_filter,
                "count": len(docs),
                "documents": docs
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error querying {collection_name}: {str(e)}")]
    
    # ========================================================================
    # run_aggregation
    # ========================================================================
    elif name == "run_aggregation":
        collection_name = arguments.get("collection")
        pipeline = arguments.get("pipeline", [])
        
        try:
            collection = db[collection_name]
            results = list(collection.aggregate(pipeline))
            
            result = {
                "collection": collection_name,
                "pipeline_stages": len(pipeline),
                "result_count": len(results),
                "results": [serialize_doc(doc) for doc in results]
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error running aggregation: {str(e)}")]
    
    # ========================================================================
    # list_predefined_stats
    # ========================================================================
    elif name == "list_predefined_stats":
        stats_list = []
        for stat_name, stat_info in AGGREGATION_PIPELINES.items():
            stats_list.append({
                "name": stat_name,
                "description": stat_info["description"],
                "collection": stat_info["collection"]
            })
        
        result = {
            "available_statistics": stats_list,
            "usage": "Use run_predefined_stats with the stat_name to execute"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    # ========================================================================
    # run_predefined_stats
    # ========================================================================
    elif name == "run_predefined_stats":
        stat_name = arguments.get("stat_name")
        
        if stat_name not in AGGREGATION_PIPELINES:
            available = ", ".join(AGGREGATION_PIPELINES.keys())
            return [TextContent(type="text", text=f"Unknown statistic: {stat_name}. Available: {available}")]
        
        stat_info = AGGREGATION_PIPELINES[stat_name]
        collection_name = stat_info["collection"]
        pipeline = stat_info["pipeline"]
        
        try:
            collection = db[collection_name]
            results = list(collection.aggregate(pipeline))
            
            result = {
                "statistic": stat_name,
                "description": stat_info["description"],
                "collection": collection_name,
                "results": [serialize_doc(doc) for doc in results]
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error running statistic: {str(e)}")]
    
    # ========================================================================
    # get_collection_sample
    # ========================================================================
    elif name == "get_collection_sample":
        collection_name = arguments.get("collection")
        limit = arguments.get("limit", 3)
        
        try:
            collection = db[collection_name]
            docs = list(collection.find().limit(limit))
            
            result = {
                "collection": collection_name,
                "sample_count": len(docs),
                "sample_documents": [serialize_doc(doc) for doc in docs]
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting sample: {str(e)}")]
    
    # ========================================================================
    # get_dashboard_stats
    # ========================================================================
    elif name == "get_dashboard_stats":
        try:
            # Total counts
            deliveries_count = db.deliveries.count_documents({})
            partners_count = db.partners.count_documents({})
            active_partners = db.partners.count_documents({"active": True})
            
            # Deliveries by status
            status_pipeline = [
                {"$group": {"_id": "$status", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]
            status_breakdown = list(db.deliveries.aggregate(status_pipeline))
            
            # Deliveries by city (top 5)
            city_pipeline = [
                {"$group": {"_id": "$address.city", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            top_cities = list(db.deliveries.aggregate(city_pipeline))
            
            # Partner workload
            partner_pipeline = [
                {"$match": {"partner_id": {"$ne": None}}},
                {"$group": {"_id": "$partner_id", "active_deliveries": {"$sum": 1}}},
                {"$sort": {"active_deliveries": -1}}
            ]
            partner_workload = list(db.deliveries.aggregate(partner_pipeline))
            
            # Pending deliveries needing dispatch
            pending_count = db.deliveries.count_documents({"status": "pending"})
            
            dashboard = {
                "summary": {
                    "total_deliveries": deliveries_count,
                    "total_partners": partners_count,
                    "active_partners": active_partners,
                    "pending_dispatch": pending_count
                },
                "status_breakdown": [serialize_doc(s) for s in status_breakdown],
                "top_cities": [serialize_doc(c) for c in top_cities],
                "partner_workload": [serialize_doc(p) for p in partner_workload]
            }
            
            return [TextContent(type="text", text=json.dumps(dashboard, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error generating dashboard: {str(e)}")]
    
    # ========================================================================
    # search_deliveries
    # ========================================================================
    elif name == "search_deliveries":
        search_term = arguments.get("search_term", "")
        
        try:
            # Try text search first
            try:
                docs = list(db.deliveries.find(
                    {"$text": {"$search": search_term}},
                    {"score": {"$meta": "textScore"}}
                ).sort([("score", {"$meta": "textScore"})]).limit(20))
            except:
                # Fallback to regex search
                regex_filter = {"$or": [
                    {"customer_name": {"$regex": search_term, "$options": "i"}},
                    {"tracking_number": {"$regex": search_term, "$options": "i"}},
                    {"address.city": {"$regex": search_term, "$options": "i"}},
                    {"delivery_id": {"$regex": search_term, "$options": "i"}}
                ]}
                docs = list(db.deliveries.find(regex_filter).limit(20))
            
            result = {
                "search_term": search_term,
                "count": len(docs),
                "deliveries": [serialize_doc(doc) for doc in docs]
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error searching: {str(e)}")]
    
    # ========================================================================
    # track_delivery
    # ========================================================================
    elif name == "track_delivery":
        identifier = arguments.get("identifier", "").strip()
        
        try:
            # Try by tracking number first
            doc = db.deliveries.find_one({"tracking_number": identifier.upper()})
            
            if not doc:
                # Try by delivery_id
                doc = db.deliveries.find_one({"delivery_id": identifier.upper()})
            
            if not doc:
                return [TextContent(type="text", text=f"No delivery found with identifier: {identifier}")]
            
            # Get partner info if assigned
            partner_info = None
            if doc.get("partner_id"):
                partner = db.partners.find_one({"partner_id": doc["partner_id"]})
                if partner:
                    partner_info = {
                        "name": partner.get("name"),
                        "phone": partner.get("contact_phone"),
                        "email": partner.get("contact_email")
                    }
            
            tracking_info = {
                "delivery_id": doc.get("delivery_id"),
                "tracking_number": doc.get("tracking_number"),
                "status": doc.get("status"),
                "status_text": doc.get("status_text"),
                "customer_name": doc.get("customer_name"),
                "delivery_address": doc.get("address"),
                "eta": str(doc.get("eta")) if doc.get("eta") else None,
                "partner": partner_info,
                "notes": doc.get("notes"),
                "events": doc.get("events", []),
                "created_at": str(doc.get("created_at"))
            }
            
            return [TextContent(type="text", text=json.dumps(serialize_doc(tracking_info), indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error tracking delivery: {str(e)}")]
    
    # ========================================================================
    # get_partner_details
    # ========================================================================
    elif name == "get_partner_details":
        partner_id = arguments.get("partner_id", "").strip()
        
        try:
            partner = db.partners.find_one({"partner_id": partner_id.upper()})
            
            if not partner:
                return [TextContent(type="text", text=f"No partner found with ID: {partner_id}")]
            
            # Get delivery stats for this partner
            delivery_stats = list(db.deliveries.aggregate([
                {"$match": {"partner_id": partner_id.upper()}},
                {"$group": {"_id": "$status", "count": {"$sum": 1}}}
            ]))
            
            total_deliveries = sum(s["count"] for s in delivery_stats)
            
            # Recent deliveries
            recent = list(db.deliveries.find(
                {"partner_id": partner_id.upper()}
            ).sort("created_at", -1).limit(5))
            
            result = {
                "partner": serialize_doc(partner),
                "statistics": {
                    "total_deliveries": total_deliveries,
                    "by_status": [serialize_doc(s) for s in delivery_stats]
                },
                "recent_deliveries": [serialize_doc(d) for d in recent]
            }
            
            return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
            
        except Exception as e:
            return [TextContent(type="text", text=f"Error getting partner details: {str(e)}")]
    
    # ========================================================================
    # Unknown tool
    # ========================================================================
    else:
        return [TextContent(type="text", text=f"Unknown tool: {name}")]


# ============================================================================
# Main
# ============================================================================

async def main():
    """Run the MCP server."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
