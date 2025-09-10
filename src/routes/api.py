from flask import Blueprint, request, jsonify
from PIL import Image, ImageDraw
from datetime import datetime
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

@api_bp.route('/config/default-prompt', methods=['GET'])
def get_default_prompt():
    """Get default AI prompt template"""
    try:
        return jsonify({'ai_prompt_template': config_service.default_config['ai_prompt_template']})
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

@api_bp.route('/display/debug-gemini', methods=['POST'])
def debug_gemini():
    """Debug Gemini API configuration and connection"""
    try:
        from google import genai as genai_new
        
        # Check API key
        gemini_api_key = config_service.get('gemini_api_key')
        if not gemini_api_key:
            return jsonify({'error': 'No Gemini API key configured'}), 400
        
        # Test client creation
        client = genai_new.Client(api_key=gemini_api_key)
        
        # Test simple text generation
        test_response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=["Say hello in exactly 5 words."],
        )
        
        test_result = test_response.text.strip()
        
        return jsonify({
            'message': 'Gemini API connection test successful',
            'api_key_present': bool(gemini_api_key),
            'api_key_length': len(gemini_api_key) if gemini_api_key else 0,
            'test_response': test_result,
            'models_available': ['gemini-2.5-flash', 'gemini-2.5-flash-image-preview']
        })
        
    except Exception as e:
        import traceback
        return jsonify({
            'error': f'Gemini API test failed: {str(e)}',
            'traceback': traceback.format_exc(),
            'api_key_present': bool(config_service.get('gemini_api_key'))
        }), 500

@api_bp.route('/display/test-hardware', methods=['POST'])
def test_display_hardware():
    """Test display hardware without AI generation"""
    try:
        # Create a simple test image
        test_image = Image.new('RGB', (800, 480), 'white')
        draw = ImageDraw.Draw(test_image)
        draw.text((50, 50), "Hardware Test Image", fill='black')
        draw.text((50, 100), f"Generated at: {datetime.now()}", fill='red')
        draw.rectangle([50, 150, 750, 430], outline='blue', width=3)
        
        # Apply dithering
        dithered_image = display_service._apply_floyd_steinberg_dithering(test_image)
        
        # Try to display it
        # Ensure display is loaded
        if not display_service.color_epd:
            display_service._ensure_display_loaded()
            
        if display_service.color_epd:
            # Reset display initialization state
            display_service.display_initialized = False
            
            # Attempt hardware display
            try:
                display_service.color_epd.init()
                display_service.display_initialized = True
                display_service.color_epd.Clear()
                buffer = display_service.color_epd.getbuffer(dithered_image)
                display_service.color_epd.display(buffer)
                display_service.color_epd.sleep()
                
                dithered_image.save('test_hardware_success.png')
                return jsonify({'message': 'Hardware display test successful', 'image_saved': 'test_hardware_success.png'})
                
            except Exception as hw_error:
                dithered_image.save('test_hardware_failed.png')
                return jsonify({
                    'error': f'Hardware display test failed: {str(hw_error)}',
                    'image_saved': 'test_hardware_failed.png'
                }), 500
        else:
            dithered_image.save('test_hardware_mock.png')
            return jsonify({'message': 'No hardware display available, test image saved', 'image_saved': 'test_hardware_mock.png'})
            
    except Exception as e:
        return jsonify({'error': f'Display hardware test failed: {str(e)}'}), 500

@api_bp.route('/display/test-i2c', methods=['POST'])
def test_i2c():
    """Test I2C communication with ESP32"""
    try:
        display_service = DisplayService()
        
        # Force cache fresh data for testing
        display_service._fetch_and_cache_data()
        
        # Test I2C communication
        display_service._send_data_to_esp32()
        
        return jsonify({
            'message': 'I2C test completed',
            'cached_weather': display_service.cached_weather_data,
            'cached_events_count': len(display_service.cached_calendar_data) if display_service.cached_calendar_data else 0,
            'i2c_initialized': display_service.i2c_initialized
        })
        
    except Exception as e:
        return jsonify({'error': f'I2C test failed: {str(e)}'}), 500

@api_bp.route('/display/force-bw-update', methods=['POST'])
def force_bw_update():
    """Force immediate B&W display update (ignores timing intervals)"""
    try:
        display_service = DisplayService()
        
        # Reset timing to force immediate update
        display_service.last_api_fetch = 0
        display_service.last_i2c_send = 0
        
        # Trigger update
        display_service.update_bw_display()
        
        return jsonify({
            'message': 'B&W display update forced',
            'weather_cached': display_service.cached_weather_data is not None,
            'events_cached': display_service.cached_calendar_data is not None,
            'i2c_available': display_service.i2c_initialized
        })
        
    except Exception as e:
        return jsonify({'error': f'B&W display update failed: {str(e)}'}), 500