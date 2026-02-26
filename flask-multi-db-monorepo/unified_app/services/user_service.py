"""
User Service - Database operations for application users (PostgreSQL)
Handles user CRUD, password hashing with bcrypt, and authentication.
"""
import psycopg2
import psycopg2.extras
import bcrypt
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.database.postgresql import get_pooled_connection


class UserService:
    """Service for application user management using PostgreSQL."""

    def __init__(self):
        pass

    def _get_connection(self):
        """Get a pooled database connection."""
        return get_pooled_connection()

    def _row_to_dict(self, row, columns) -> Dict[str, Any]:
        """Convert a database row to a dictionary."""
        result = {}
        for i, col in enumerate(columns):
            value = row[i]
            if isinstance(value, datetime):
                value = value.isoformat()
            elif isinstance(value, uuid.UUID):
                value = str(value)
            result[col] = value
        return result

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """Verify a password against its bcrypt hash."""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    def ensure_table(self):
        """Create the app_users table if it does not exist."""
        ddl = """
        CREATE TABLE IF NOT EXISTS app_users (
            user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(100) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash VARCHAR(255) NOT NULL,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(ddl)
                conn.commit()
        except Exception as e:
            print(f"[UserService] ensure_table error: {e}")

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate a user by email and password.
        Returns the user dict if valid, None otherwise.
        """
        user = self.get_user_by_email(email)
        if not user:
            return None
        if not user.get('is_active', True):
            return None
        if self.verify_password(password, user['password_hash']):
            return user
        return None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def get_all_users(self) -> List[Dict[str, Any]]:
        """Return all users (without password hashes)."""
        query = """
            SELECT user_id, username, email, is_active, created_at, updated_at
            FROM app_users
            ORDER BY created_at
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query)
                    columns = [desc[0] for desc in cur.description]
                    return [self._row_to_dict(row, columns) for row in cur.fetchall()]
        except Exception as e:
            print(f"[UserService] get_all_users error: {e}")
            return []

    def search_users(self, search: str = '', page: int = 1, per_page: int = 20) -> tuple:
        """Search users by name/email with pagination, ordered by username.

        Returns (users_list, total_count).
        """
        offset = (page - 1) * per_page
        params: list = []

        where_clause = ""
        if search:
            where_clause = "WHERE LOWER(username) LIKE %s OR LOWER(email) LIKE %s"
            like_pattern = f"%{search.lower()}%"
            params = [like_pattern, like_pattern]

        count_query = f"SELECT COUNT(*) FROM app_users {where_clause}"
        data_query = f"""
            SELECT user_id, username, email, is_active, created_at, updated_at
            FROM app_users
            {where_clause}
            ORDER BY LOWER(username)
            LIMIT %s OFFSET %s
        """

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(count_query, params)
                    total = cur.fetchone()[0]

                    cur.execute(data_query, params + [per_page, offset])
                    columns = [desc[0] for desc in cur.description]
                    users = [self._row_to_dict(row, columns) for row in cur.fetchall()]

            return users, total
        except Exception as e:
            print(f"[UserService] search_users error: {e}")
            return [], 0

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get a single user by ID."""
        query = """
            SELECT user_id, username, email, is_active, created_at, updated_at
            FROM app_users
            WHERE user_id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (user_id,))
                    row = cur.fetchone()
                    if row:
                        columns = [desc[0] for desc in cur.description]
                        return self._row_to_dict(row, columns)
            return None
        except Exception as e:
            print(f"[UserService] get_user_by_id error: {e}")
            return None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Get a user by email (includes password_hash for authentication)."""
        query = """
            SELECT user_id, username, email, password_hash, is_active, created_at, updated_at
            FROM app_users
            WHERE email = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (email,))
                    row = cur.fetchone()
                    if row:
                        columns = [desc[0] for desc in cur.description]
                        return self._row_to_dict(row, columns)
            return None
        except Exception as e:
            print(f"[UserService] get_user_by_email error: {e}")
            return None

    def create_user(self, username: str, email: str, password: str) -> Optional[str]:
        """Create a new user. Returns the user_id or None on failure."""
        password_hash = self.hash_password(password)
        query = """
            INSERT INTO app_users (username, email, password_hash)
            VALUES (%s, %s, %s)
            RETURNING user_id
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (username, email, password_hash))
                    user_id = cur.fetchone()[0]
                conn.commit()
                return str(user_id)
        except psycopg2.errors.UniqueViolation:
            raise ValueError("A user with that username or email already exists.")
        except Exception as e:
            print(f"[UserService] create_user error: {e}")
            raise

    def update_user(self, user_id: str, username: str, email: str, is_active: bool = True) -> bool:
        """Update user profile (not password)."""
        query = """
            UPDATE app_users
            SET username = %s, email = %s, is_active = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (username, email, is_active, user_id))
                    updated = cur.rowcount > 0
                conn.commit()
                return updated
        except psycopg2.errors.UniqueViolation:
            raise ValueError("A user with that username or email already exists.")
        except Exception as e:
            print(f"[UserService] update_user error: {e}")
            raise

    def change_password(self, user_id: str, new_password: str) -> bool:
        """Change a user's password."""
        password_hash = self.hash_password(new_password)
        query = """
            UPDATE app_users
            SET password_hash = %s, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = %s
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (password_hash, user_id))
                    updated = cur.rowcount > 0
                conn.commit()
                return updated
        except Exception as e:
            print(f"[UserService] change_password error: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        query = "DELETE FROM app_users WHERE user_id = %s"
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query, (user_id,))
                    deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        except Exception as e:
            print(f"[UserService] delete_user error: {e}")
            return False

    def count_users(self) -> int:
        """Return the total number of users."""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM app_users")
                    return cur.fetchone()[0]
        except Exception as e:
            print(f"[UserService] count_users error: {e}")
            return 0
