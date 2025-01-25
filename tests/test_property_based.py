from hypothesis import given, strategies as st
from hypothesis.extra.datetime import datetimes
from datetime import datetime, timedelta, timezone
import uuid

"""
Property-Based Tests Using Hypothesis

Validates system invariants through generated test cases:
- Filter matching properties
- RSS item structure validation
- Database recency checks
- Configuration edge cases
"""

@given(
    st.integers(min_value=0, max_value=1000),  # days_ago
    st.text(min_size=1),                       # title
    st.decimals(min_value=0),                  # price
    st.urls()                                  # url
)
def test_ad_recency_properties(days_ago, title, price, url):
    monitor = create_test_monitor()
    ad_id = str(uuid.uuid4())
    
    with monitor.get_db_connection() as conn:
        cursor = conn.cursor()
        test_time = datetime.now(timezone.utc) - timedelta(days=days_ago)
        
        # Property: Ad should be considered recent if within 7 days
        is_recent = days_ago < 7
        assert monitor._is_ad_recent(cursor, ad_id, test_time) == is_recent 