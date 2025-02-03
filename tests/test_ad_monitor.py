"""
Unit Tests for Facebook Marketplace RSS Monitor

Covers:
- Selenium content fetching
- Database operations
- Filter matching logic
- Concurrent job handling
- Error scenarios and recovery
"""

import pytest
from unittest.mock import patch, Mock
from fb_ad_monitor import fbRssAdMonitor
import json
from pathlib import Path

@pytest.fixture
def monitor(tmp_path):
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

@pytest.mark.selenium
def test_selenium_content_fetch(monitor):
    monitor.init_selenium()
    
    # Add test URL to monitored list
    test_url = "https://www.facebook.com/marketplace"
    monitor.urls_to_monitor = [test_url]
    
    # Mock successful Facebook page structure
    with patch('selenium.webdriver.Firefox') as mock_driver:
        mock_driver.page_source = "<html><div class='x78zum5 xdt5ytf'>Test Content</div></html>"
        result = monitor.get_page_content(test_url)
        assert result is not None

def test_selenium_headless_mode(monitor):
    with patch('selenium.webdriver.Firefox') as mock_driver:
        monitor.init_selenium()
        args = mock_driver.call_args[1]['options'].arguments 