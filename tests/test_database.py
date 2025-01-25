import sqlite3
from pathlib import Path

def test_database_schema_migration(tmp_path):
    db_path = tmp_path / "test.db"
    
    # Create old schema
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE ad_changes (id INTEGER PRIMARY KEY)")
    
    # Initialize with new schema
    with get_db_connection(str(db_path)) as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(ad_changes)")
        columns = [col[1] for col in cursor.fetchall()]
        assert 'last_checked' in columns 