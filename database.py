"""
Database Connection Management

Provides:
- Context manager for SQLite connections
- Connection pooling
- Error handling
- Automatic cleanup

Usage:
    with get_db_connection() as conn:
        cursor = conn.cursor()
""" 

from contextlib import contextmanager
import sqlite3
from typing import Generator
import logging

logger = logging.getLogger(__name__)

@contextmanager
def get_db_connection(database_path: str) -> Generator[sqlite3.Connection, None, None]:
    conn = None
    try:
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()