import requests
from typing import Dict, Any, List
from src.services.config_service import ConfigService

class WeatherService:
    def __init__(self):
        self.config_service = ConfigService()
        self.base_url = "http://api.openweathermap.org/data/2.5"
    
    def _get_api_key(self) -> str:
        """Get OpenWeather API key from config"""
        api_key = self.config_service.get('openweather_api_key')
        if not api_key:
            raise ValueError("OpenWeather API key not configured")
        return api_key
    
    def _get_location(self) -> str:
        """Get weather location from config"""
        location = self.config_service.get('weather_location', 'Berlin')
        return location
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make API request to OpenWeather"""
        params['appid'] = self._get_api_key()
        params['units'] = 'metric'  # Use Celsius
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Weather API request failed: {str(e)}")
    
    def get_current_weather(self) -> Dict[str, Any]:
        """Get current weather data"""
        try:
            location = self._get_location()
            
            data = self._make_request('weather', {'q': location})
            
            return {
                'location': data['name'],
                'country': data['sys']['country'],
                'temperature': round(data['main']['temp']),
                'feels_like': round(data['main']['feels_like']),
                'humidity': data['main']['humidity'],
                'pressure': data['main']['pressure'],
                'description': data['weather'][0]['description'].title(),
                'main': data['weather'][0]['main'],
                'icon': data['weather'][0]['icon'],
                'wind_speed': round(data['wind']['speed'], 1),
                'wind_direction': data['wind'].get('deg', 0),
                'visibility': data.get('visibility', 10000) / 1000,  # Convert to km
                'uv_index': None,  # Current weather doesn't include UV index
                'timestamp': data['dt']
            }
            
        except Exception as e:
            print(f"Error fetching current weather: {e}")
            return {
                'location': 'Unknown',
                'temperature': 0,
                'feels_like': 0,
                'humidity': 0,
                'description': 'Weather data unavailable',
                'error': str(e)
            }
    
    def get_forecast(self, days: int = 5) -> Dict[str, Any]:
        """Get weather forecast"""
        try:
            location = self._get_location()
            
            data = self._make_request('forecast', {'q': location})
            
            # Process forecast data (OpenWeather gives 5-day forecast with 3-hour intervals)
            forecasts = []
            current_date = None
            daily_data = []
            
            for item in data['list']:
                forecast_date = item['dt_txt'].split(' ')[0]
                
                if current_date != forecast_date:
                    if daily_data:
                        # Process previous day's data
                        daily_forecast = self._process_daily_forecast(daily_data)
                        daily_forecast['date'] = current_date
                        forecasts.append(daily_forecast)
                    
                    current_date = forecast_date
                    daily_data = []
                
                daily_data.append(item)
            
            # Don't forget the last day
            if daily_data:
                daily_forecast = self._process_daily_forecast(daily_data)
                daily_forecast['date'] = current_date
                forecasts.append(daily_forecast)
            
            return {
                'location': data['city']['name'],
                'country': data['city']['country'],
                'forecasts': forecasts[:days]  # Limit to requested days
            }
            
        except Exception as e:
            print(f"Error fetching weather forecast: {e}")
            return {
                'location': 'Unknown',
                'forecasts': [],
                'error': str(e)
            }
    
    def _process_daily_forecast(self, day_data: List[Dict]) -> Dict[str, Any]:
        """Process 3-hourly data into daily summary"""
        if not day_data:
            return {}
        
        # Extract temperatures
        temps = [item['main']['temp'] for item in day_data]
        
        # Find the most common weather condition
        weather_counts = {}
        for item in day_data:
            weather = item['weather'][0]['main']
            weather_counts[weather] = weather_counts.get(weather, 0) + 1
        
        most_common_weather = max(weather_counts, key=weather_counts.get)
        
        # Get the corresponding description and icon
        weather_item = next(
            (item['weather'][0] for item in day_data if item['weather'][0]['main'] == most_common_weather),
            day_data[0]['weather'][0]
        )
        
        return {
            'temp_min': round(min(temps)),
            'temp_max': round(max(temps)),
            'temp_avg': round(sum(temps) / len(temps)),
            'humidity': round(sum(item['main']['humidity'] for item in day_data) / len(day_data)),
            'description': weather_item['description'].title(),
            'main': weather_item['main'],
            'icon': weather_item['icon'],
            'wind_speed': round(sum(item['wind']['speed'] for item in day_data) / len(day_data), 1)
        }
    
    def get_weather_summary_for_ai(self) -> str:
        """Get weather summary for AI image generation"""
        try:
            current = self.get_current_weather()
            forecast = self.get_forecast(days=1)
            
            summary_parts = [
                f"Current weather in {current['location']}: {current['temperature']}°C, {current['description']}"
            ]
            
            if forecast['forecasts']:
                today_forecast = forecast['forecasts'][0]
                summary_parts.append(
                    f"Today's forecast: {today_forecast['temp_min']}-{today_forecast['temp_max']}°C, {today_forecast['description']}"
                )
            
            return ". ".join(summary_parts)
            
        except Exception as e:
            return f"Weather information unavailable: {str(e)}"