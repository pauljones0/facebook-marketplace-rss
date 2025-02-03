from dataclasses import dataclass
from typing import Dict, List, Optional

"""
Application Configuration Management

Defines:
- Config data classes
- Search filter structures
- Configuration validation
- JSON serialization/deserialization

Usage:
    Config.from_dict() -> Config: Create config from JSON data
"""

@dataclass
class SearchFilter:
    level1: List[str]
    level2: Optional[List[str]] = None
    level3: Optional[List[str]] = None

@dataclass
class Config:
    server_ip: str
    server_port: str
    currency: str
    refresh_interval_minutes: int
    log_filename: str
    base_url: str
    locale: Optional[str]
    searches: Dict[str, SearchFilter]
    request_delay_seconds: Optional[int] = None
    log_level: Optional[str] = "INFO"
    debug: Optional[bool] = False

    @classmethod
    def from_dict(cls, data: dict) -> 'Config':
        searches = {
            name: SearchFilter(**filters)
            for name, filters in data.get('searches', {}).items()
        }
        return cls(
            server_ip=data['server_ip'],
            server_port=data['server_port'],
            currency=data['currency'],
            refresh_interval_minutes=data['refresh_interval_minutes'],
            log_filename=data['log_filename'],
            base_url=data['base_url'],
            locale=data.get('locale'),
            searches=searches,
            request_delay_seconds=data.get('request_delay_seconds'),
            log_level=data.get('log_level', 'INFO'),
            debug=data.get('debug', False)
        ) 