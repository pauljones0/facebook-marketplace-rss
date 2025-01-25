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
            searches=searches
        ) 