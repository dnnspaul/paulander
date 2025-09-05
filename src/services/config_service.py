import json
import os
from typing import Dict, Any

class ConfigService:
    def __init__(self):
        self.config_file = 'config.json'
        self.default_config = {
            'apple_id': '',
            'app_password': '',
            'calendar_url': '',
            'weather_location': 'Berlin',
            'openweather_api_key': os.getenv('OPENWEATHER_API_KEY', ''),
            'gemini_api_key': os.getenv('GEMINI_API_KEY', ''),
            'display_refresh_interval': 1800,  # 30 minutes in seconds
            'color_display_refresh_time': '06:00'
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get current configuration"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                # Merge with defaults to ensure all keys exist
                merged_config = self.default_config.copy()
                merged_config.update(config)
                return merged_config
            except (json.JSONDecodeError, IOError):
                return self.default_config.copy()
        return self.default_config.copy()
    
    def update_config(self, new_config: Dict[str, Any]) -> None:
        """Update configuration"""
        current_config = self.get_config()
        current_config.update(new_config)
        
        with open(self.config_file, 'w') as f:
            json.dump(current_config, f, indent=2)
    
    def get(self, key: str, default=None):
        """Get a specific config value"""
        config = self.get_config()
        return config.get(key, default)