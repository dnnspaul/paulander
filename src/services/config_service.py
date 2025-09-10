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
            'color_display_refresh_time': '06:00',
            'ai_prompt_template': '''I want you to write a detailed prompt for an AI to generate a modern painting that is being shown on an 7.3" e-ink display that supports 6 colors (black, white, red, green, blue, yellow) with a resolution of 800x480. The generated image should reflect today.

*Todays information*
Date: {today_date}
Weather: {weather_summary}
Calendar events:
{events_text}

ONLY RETURN YOUR PROMPT SUGGESTION, WITHOUT ANYTHING ELSE (DISMISS SOMETHING LIKE `Here's your prompt`).
**Never** mention the e-ink display, because it will result in an e-ink display being rendered. Also make sure, that an artistic painting is generated instead of anything that looks like an info screen.
Always generate a single picture and never split it into multiple images. Try to combine every occassion that the calendar, the weather and the date has to offer into a single image.

Make it vintage-poster style. Let it only generate an image without any text that is drawn onto the image like title, date or something like that.'''
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