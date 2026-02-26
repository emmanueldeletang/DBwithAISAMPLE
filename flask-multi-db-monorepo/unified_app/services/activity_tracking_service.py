"""
Activity Tracking Service - Stores user activity per day in Azure Cosmos DB (NoSQL API).

Each document represents one day of activity for a single user.
- Partition key: user email
- Document id: {email}_{YYYY-MM-DD}
- Activities array: list of {page, action, timestamp, details}
"""
import os
from datetime import datetime, timezone
from azure.cosmos import CosmosClient, PartitionKey, exceptions


# Cosmos DB NoSQL configuration
COSMOS_ENDPOINT = os.getenv(    "COSMOS_NOSQL_ENDPOINT")
COSMOS_KEY = os.getenv(    "COSMOS_NOSQL_KEY")
DATABASE_NAME = os.getenv("COSMOS_NOSQL_DATABASE")
CONTAINER_NAME = os.getenv("COSMOS_NOSQL_CONTAINER")


class ActivityTrackingService:
    """Tracks user activities in Azure Cosmos DB NoSQL, one document per user per day."""

    def __init__(self):
        self._client = None
        self._container = None

    # ------------------------------------------------------------------
    # Lazy initialisation (avoids issues at import time)
    # ------------------------------------------------------------------

    def _get_container(self):
        """Return (and cache) the Cosmos container, creating DB/container if needed."""
        if self._container is not None:
            return self._container

        self._client = CosmosClient(COSMOS_ENDPOINT, credential=COSMOS_KEY)

        # Ensure database exists
        db = self._client.create_database_if_not_exists(id=DATABASE_NAME)

        # Ensure container exists – partition key is /email
        indexing_policy = {
            "compositeIndexes": [
                [
                    {"path": "/email", "order": "ascending"},
                    {"path": "/date", "order": "ascending"},
                ]
            ]
        }
        self._container = db.create_container_if_not_exists(
            id=CONTAINER_NAME,
            partition_key=PartitionKey(path="/email"),
            offer_throughput=400,
            indexing_policy=indexing_policy,
        )
        return self._container

    # ------------------------------------------------------------------
    # Core: record an activity
    # ------------------------------------------------------------------

    def track(self, email: str, page: str, action: str, details: str | None = None):
        """
        Append an activity entry to today's document for *email*.

        Uses a Cosmos DB patch operation (single round-trip) when the daily
        document already exists, falling back to a create on the first activity
        of the day.

        Parameters
        ----------
        email   : User email (partition key).
        page    : The route / URL the user visited (e.g. "/products").
        action  : Short verb describing what happened (e.g. "view", "create", "delete").
        details : Optional free-text with extra info (e.g. "Created product SKU-001").
        """
        if not email:
            return

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        doc_id = f"{email}_{today}"

        activity_entry = {
            "page": page,
            "action": action,
            "timestamp": now.isoformat(),
        }
        if details:
            activity_entry["details"] = details

        container = self._get_container()

        # Use patch_item to atomically append to the activities array and
        # update last_activity in a single round-trip.  Fall back to
        # create_item when the document does not yet exist for today.
        patch_operations = [
            {"op": "add", "path": "/activities/-", "value": activity_entry},
            {"op": "set", "path": "/last_activity", "value": now.isoformat()},
        ]
        try:
            container.patch_item(
                item=doc_id,
                partition_key=email,
                patch_operations=patch_operations,
            )
        except exceptions.CosmosResourceNotFoundError:
            # First activity of the day – create a new document
            new_doc = {
                "id": doc_id,
                "email": email,
                "date": today,
                "activities": [activity_entry],
                "first_activity": now.isoformat(),
                "last_activity": now.isoformat(),
            }
            try:
                container.create_item(body=new_doc)
            except exceptions.CosmosResourceExistsError:
                # Race condition: another request created the doc concurrently;
                # retry the patch once.
                try:
                    container.patch_item(
                        item=doc_id,
                        partition_key=email,
                        patch_operations=patch_operations,
                    )
                except Exception as exc:
                    print(f"[ActivityTracking] Error on retry patch: {exc}")
        except Exception as exc:
            # Log but never let tracking failures break the main application
            print(f"[ActivityTracking] Error tracking activity: {exc}")


    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def get_activities_for_day(self, email: str, date_str: str | None = None):
        """
        Return the activity document for a specific user and day.

        Parameters
        ----------
        email    : User email.
        date_str : Date string YYYY-MM-DD (defaults to today UTC).
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        doc_id = f"{email}_{date_str}"
        container = self._get_container()

        try:
            return container.read_item(item=doc_id, partition_key=email)
        except exceptions.CosmosResourceNotFoundError:
            return None
        except Exception as exc:
            print(f"[ActivityTracking] Error reading activities: {exc}")
            return None

    def get_recent_activities(self, email: str, days: int = 7):
        """
        Return the last *days* activity documents for a user (most recent first).
        """
        container = self._get_container()
        query = (
            "SELECT * FROM c WHERE c.email = @email "
            "ORDER BY c.date DESC OFFSET 0 LIMIT @limit"
        )
        params = [
            {"name": "@email", "value": email},
            {"name": "@limit", "value": days},
        ]
        try:
            items = list(
                container.query_items(
                    query=query,
                    parameters=params,
                    partition_key=email,
                )
            )
            return items
        except Exception as exc:
            print(f"[ActivityTracking] Error querying activities: {exc}")
            return []

    def get_all_activities_for_day(self, date_str: str | None = None):
        """
        Return all activity documents for a given day (cross-partition).
        Used by the admin UI to see every user's activity on a specific date.
        """
        if date_str is None:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        container = self._get_container()
        query = "SELECT * FROM c WHERE c.date = @date ORDER BY c.last_activity DESC"
        params = [{"name": "@date", "value": date_str}]
        try:
            items = list(
                container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True,
                )
            )
            return items
        except Exception as exc:
            print(f"[ActivityTracking] Error querying all activities for day: {exc}")
            return []

    def get_distinct_emails(self):
        """
        Return a list of distinct user emails that have activity records.
        """
        container = self._get_container()
        query = "SELECT DISTINCT c.email FROM c"
        try:
            items = list(
                container.query_items(
                    query=query,
                    enable_cross_partition_query=True,
                )
            )
            return sorted(set(item["email"] for item in items))
        except Exception as exc:
            print(f"[ActivityTracking] Error querying distinct emails: {exc}")
            return []
