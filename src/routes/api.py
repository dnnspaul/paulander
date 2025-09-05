from flask import Blueprint, request, jsonify
from PIL import Image, ImageDraw
from src.services.calendar_service import CalendarService
from src.services.weather_service import WeatherService
from src.services.config_service import ConfigService
from src.services.display_service import DisplayService

api_bp = Blueprint('api', __name__)

config_service = ConfigService()
calendar_service = CalendarService()
weather_service = WeatherService()
display_service = DisplayService()

@api_bp.route('/config', methods=['GET'])
def get_config():
    """Get current configuration"""
    try:
        config = config_service.get_config()
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/config', methods=['POST'])
def update_config():
    """Update configuration"""
    try:
        data = request.get_json()
        config_service.update_config(data)
        return jsonify({'message': 'Configuration updated successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/calendar/test', methods=['POST'])
def test_calendar():
    """Test calendar connection"""
    try:
        data = request.get_json()
        apple_id = data.get('apple_id')
        app_password = data.get('app_password')
        
        result = calendar_service.test_connection(apple_id, app_password)
        return jsonify({'success': result['success'], 'message': result['message']})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/calendar/events', methods=['GET'])
def get_calendar_events():
    """Get upcoming calendar events"""
    try:
        events = calendar_service.get_upcoming_events()
        return jsonify({'events': events})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/weather', methods=['GET'])
def get_weather():
    """Get current weather data"""
    try:
        weather = weather_service.get_current_weather()
        return jsonify(weather)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/weather/forecast', methods=['GET'])
def get_weather_forecast():
    """Get weather forecast"""
    try:
        forecast = weather_service.get_forecast()
        return jsonify(forecast)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/display/refresh', methods=['POST'])
def refresh_display():
    """Manually refresh displays"""
    try:
        display_type = request.get_json().get('type', 'both')
        result = display_service.refresh_display(display_type)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/display/status', methods=['GET'])
def get_display_status():
    """Get display status"""
    try:
        status = display_service.get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/display/test-ai-image', methods=['POST'])
def test_ai_image():
    """Test AI image generation"""
    try:
        image = display_service.generate_daily_image()
        image.save('test_ai_generated_image_dithered.png')
        return jsonify({'message': 'AI image generated successfully with Floyd-Steinberg dithering and saved as test_ai_generated_image_dithered.png'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@api_bp.route('/display/test-dithering', methods=['POST'])
def test_dithering():
    """Test Floyd-Steinberg dithering on fallback image"""
    try:
        # Generate fallback image without dithering for comparison
        fallback_image = display_service._create_fallback_color_image("Test weather", [])
        
        # Save original fallback image
        original_image = Image.new('RGB', (display_service.COLOR_WIDTH, display_service.COLOR_HEIGHT), 'white')
        draw = ImageDraw.Draw(original_image)
        draw.text((50, 50), "Original (no dithering)", fill='black')
        original_image.save('test_original_image.png')
        
        # Save dithered image
        fallback_image.save('test_dithered_image.png')
        
        return jsonify({'message': 'Dithering test completed. Check test_original_image.png vs test_dithered_image.png'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500