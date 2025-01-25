import pytest

@pytest.mark.parametrize("missing_field", [
    "server_ip", "server_port", "currency", "refresh_interval_minutes"
])
def test_missing_required_config_fields(missing_field):
    test_data = {
        "server_ip": "0.0.0.0",
        "server_port": "5000",
        "currency": "CA$",
        "refresh_interval_minutes": 15,
        "log_filename": "test.log",
        "base_url": "https://www.facebook.com/marketplace",
        "searches": {}
    }
    test_data.pop(missing_field)
    with pytest.raises(KeyError):
        Config.from_dict(test_data) 