from hypothesis import given, strategies as st
from datetime import datetime, timedelta, timezone
import uuid
import json
from pathlib import Path
import tempfile
from fb_ad_monitor import fbRssAdMonitor

"""
Property-Based Tests Using Hypothesis

Validates system invariants through generated test cases:
- Filter matching properties
- RSS item structure validation
- Database recency checks
- Configuration edge cases
"""

def create_test_monitor(tmp_path):
    test_config = {
        "server_ip": "0.0.0.0",
        "server_port": "5000", 
        "currency": "CA$",
        "refresh_interval_minutes": 15,
        "log_filename": "test.log",
        "base_url": "https://www.facebook.com/marketplace",
        "searches": {}
    }
    
    # Create temporary config file
    config_path = tmp_path / "test_config.json"
    with open(config_path, 'w') as f:
        json.dump(test_config, f)
    
    return fbRssAdMonitor(json_file=str(config_path))

@given(
    st.integers(min_value=0, max_value=1000),  # days_ago
    st.text(min_size=1),                       # title
    st.decimals(min_value=0).filter(lambda x: x.is_finite()),  # Exclude NaN
    st.from_regex(r"https?://\w+\.\w+")         # Basic URL pattern
)
def test_ad_recency_properties(days_ago, title, price, url):
    with tempfile.TemporaryDirectory() as tmpdir:
        monitor = create_test_monitor(Path(tmpdir))
        ad_id = str(uuid.uuid4())
        
        # Insert test data first
        with monitor.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ad_changes 
                (ad_id, url, last_checked)
                VALUES (?, ?, ?)
            ''', (ad_id, url, (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()))
            conn.commit()

        test_time = datetime.now(timezone.utc) - timedelta(days=7)
        assert monitor._is_ad_recent(cursor, ad_id, test_time) == (days_ago < 7) 