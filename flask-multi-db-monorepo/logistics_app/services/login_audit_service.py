"""
Login Audit Service - Logs all login events to MongoDB.
Collection: login_audit
"""
from pymongo import MongoClient, DESCENDING
from typing import List, Dict, Any, Optional
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.config import mongodb_config


class LoginAuditService:
    """Service for logging login events to MongoDB."""

    COLLECTION = "login_audit"

    def __init__(self):
        self.config = mongodb_config
        self._client = None
        self._db = None

    def _get_db(self):
        """Get database connection (lazy init, reuse)."""
        if self._client is None:
            self._client = MongoClient(self.config.connection_string)
            self._db = self._client[self.config.database]
        return self._db

    def log_login(self, email: str, ip: str, method: str, user_agent: str = "", success: bool = True, details: str = ""):
        """
        Record a login event.

        Args:
            email: User email address.
            ip: Client IP address.
            method: Login method ('demo', 'microsoft_devmode', 'azure_ad').
            user_agent: Browser User-Agent string.
            success: Whether the login succeeded.
            details: Optional extra info (error message, etc.).
        """
        doc = {
            "email": email,
            "ip": ip,
            "method": method,
            "user_agent": user_agent,
            "success": success,
            "timestamp": datetime.utcnow(),
        }
        if details:
            doc["details"] = details

        try:
            db = self._get_db()
            db[self.COLLECTION].insert_one(doc)
        except Exception as e:
            # Never let audit logging break the login flow
            print(f"[LoginAudit] Failed to log login event: {e}")

    def get_recent_logins(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return the most recent login events."""
        try:
            db = self._get_db()
            cursor = db[self.COLLECTION].find().sort("timestamp", DESCENDING).limit(limit)
            results = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if isinstance(doc.get("timestamp"), datetime):
                    doc["timestamp"] = doc["timestamp"].isoformat()
                results.append(doc)
            return results
        except Exception as e:
            print(f"[LoginAudit] Failed to fetch login events: {e}")
            return []

    def get_logins_by_email(self, email: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return login events for a specific email."""
        try:
            db = self._get_db()
            cursor = (
                db[self.COLLECTION]
                .find({"email": email})
                .sort("timestamp", DESCENDING)
                .limit(limit)
            )
            results = []
            for doc in cursor:
                doc["_id"] = str(doc["_id"])
                if isinstance(doc.get("timestamp"), datetime):
                    doc["timestamp"] = doc["timestamp"].isoformat()
                results.append(doc)
            return results
        except Exception as e:
            print(f"[LoginAudit] Failed to fetch login events: {e}")
            return []

    def get_statistics(self) -> Dict[str, Any]:
        """Return aggregated statistics for the audit log."""
        try:
            db = self._get_db()
            col = db[self.COLLECTION]

            total = col.count_documents({})

            # --- By user (top 15) ---
            by_user = list(col.aggregate([
                {"$group": {"_id": "$email", "count": {"$sum": 1},
                             "last_login": {"$max": "$timestamp"}}},
                {"$sort": {"count": -1}},
                {"$limit": 15}
            ]))
            for u in by_user:
                if isinstance(u.get("last_login"), datetime):
                    u["last_login"] = u["last_login"].isoformat()

            # --- By IP (top 15) ---
            by_ip = list(col.aggregate([
                {"$group": {"_id": "$ip", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}},
                {"$limit": 15}
            ]))

            # --- By method ---
            by_method = list(col.aggregate([
                {"$group": {"_id": "$method", "count": {"$sum": 1}}},
                {"$sort": {"count": -1}}
            ]))

            # --- By day (last 30 days) ---
            by_day = list(col.aggregate([
                {"$group": {
                    "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$timestamp"}},
                    "count": {"$sum": 1}
                }},
                {"$sort": {"_id": -1}},
                {"$limit": 30}
            ]))

            return {
                "total": total,
                "by_user": by_user,
                "by_ip": by_ip,
                "by_method": by_method,
                "by_day": by_day,
            }
        except Exception as e:
            print(f"[LoginAudit] Failed to compute statistics: {e}")
            return {"total": 0, "by_user": [], "by_ip": [], "by_method": [], "by_day": []}
