import pytest
import json
from pathlib import Path
from config import Config
from fb_ad_monitor import fbRssAdMonitor

@pytest.mark.parametrize("missing_field", [
    "server_ip", "server_port", "currency", "refresh_interval_minutes"
])
def test_missing_required_config_fields(tmp_path, missing_field):
    valid_config = {
        "server_ip": "0.0.0.0",
        "server_port": "5000",
        "currency": "CA$",
        "refresh_interval_minutes": 15,
        "log_filename": "test.log",
        "base_url": "https://www.facebook.com/marketplace",
        "searches": {}
    }
    
    # Create a temporary valid config file for Selenium initialization
    valid_config_path = tmp_path / "valid_config.json"
    with open(valid_config_path, 'w') as f:
        json.dump(valid_config, f)
    
    # Initialize the Selenium driver before testing
    monitor = fbRssAdMonitor(json_file=str(valid_config_path))
    monitor.init_selenium()  # Initialize the driver before testing
    
    # Prepare test config data with a missing required field
    test_data = valid_config.copy()
    test_data.pop(missing_field)
    
    # Create temporary invalid config file
    config_path = tmp_path / "test_config.json"
    with open(config_path, 'w') as f:
        json.dump(test_data, f)
    
    with pytest.raises(KeyError):
        Config.from_dict(test_data)