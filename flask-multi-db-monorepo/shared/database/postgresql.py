from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
import os
import threading
import psycopg2
from psycopg2 import pool as pg_pool

DATABASE_URL = os.getenv('POSTGRESQL_DATABASE_URL')

engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
Base = declarative_base()

def init_db():
    Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------------------------
# Shared PostgreSQL connection pool
# ---------------------------------------------------------------------------

_pool_lock = threading.Lock()
_pg_pool: pg_pool.ThreadedConnectionPool | None = None


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    """Return the module-level ThreadedConnectionPool, creating it on first call."""
    global _pg_pool
    if _pg_pool is None:
        with _pool_lock:
            if _pg_pool is None:
                from shared.config import postgres_config
                _pg_pool = pg_pool.ThreadedConnectionPool(
                    minconn=2,
                    maxconn=10,
                    host=postgres_config.host,
                    port=postgres_config.port,
                    database=postgres_config.database,
                    user=postgres_config.user,
                    password=postgres_config.password,
                    sslmode='require',
                )
    return _pg_pool


class _PooledConnection:
    """Wraps a psycopg2 connection borrowed from the pool.

    Supports both context-manager usage::

        with get_pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
            conn.commit()

    and direct usage (like existing NL-query code)::

        conn = get_pooled_connection()
        cur = conn.cursor()
        cur.execute(...)
        conn.commit()
        conn.close()  # returns connection to the pool
    """

    def __init__(self) -> None:
        # Allocate immediately so both context-manager and direct usage work.
        self._conn = _get_pool().getconn()

    def __enter__(self):
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._conn is not None:
            if exc_type is not None:
                try:
                    self._conn.rollback()
                except Exception:
                    pass
            _get_pool().putconn(self._conn)
            self._conn = None
        return False

    def cursor(self, *args, **kwargs):
        return self._conn.cursor(*args, **kwargs)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        """Return the connection to the pool (does not close the underlying socket)."""
        if self._conn is not None:
            _get_pool().putconn(self._conn)
            self._conn = None


def get_pooled_connection() -> _PooledConnection:
    """Return a context-manager that provides a pooled psycopg2 connection.

    Usage::

        with get_pooled_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)
            conn.commit()
    """
    return _PooledConnection()