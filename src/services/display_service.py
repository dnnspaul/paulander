import os
import sys
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from typing import Dict, Any, List
import google.generativeai as genai
from src.services.config_service import ConfigService
from src.services.weather_service import WeatherService
from src.services.calendar_service import CalendarService

# Add the waveshare library path
waveshare_lib_path = os.path.join(os.path.dirname(__file__), '../../waveshare-epaper/RaspberryPi_JetsonNano/python/lib')
sys.path.append(waveshare_lib_path)

# Check if we should force mock mode (useful for development)
FORCE_MOCK_DISPLAY = os.getenv('FORCE_MOCK_DISPLAY', 'false').lower() == 'true'

# Debug: Check if the path exists
if os.path.exists(waveshare_lib_path):
    print(f"Waveshare library path exists: {waveshare_lib_path}")
    # List contents for debugging
    try:
        contents = os.listdir(waveshare_lib_path)
        print(f"Library contents: {contents}")
    except Exception as e:
        print(f"Error listing directory: {e}")
else:
    print(f"Waveshare library path not found: {waveshare_lib_path}")

if FORCE_MOCK_DISPLAY:
    print("FORCE_MOCK_DISPLAY is enabled - display functions will be mocked")
    epd7in3e = None
else:
    try:
        # Check if required system libraries are available
        import RPi.GPIO as GPIO
        import spidev
        import gpiozero
        print("RPi.GPIO, spidev, and gpiozero available")
        
        # Clean up any existing GPIO state before importing
        try:
            GPIO.cleanup()
            print("Cleaned up existing GPIO state")
        except:
            pass
        
        # Try to import the waveshare library
        from waveshare_epd import epd7in3e
        print("Successfully imported epd7in3e module")
        
    except ImportError as e:
        print(f"Warning: Waveshare e-paper library not available: {e}")
        print("Display functions will be mocked.")
        print("Make sure all dependencies are installed: uv sync --extra rpi")
        print("Or manually: pip install RPi.GPIO spidev gpiozero")
        epd7in3e = None
        
    except RuntimeError as e:
        print(f"Warning: GPIO hardware initialization failed: {e}")
        print("Display functions will be mocked.")
        print("GPIO pin conflict detected. Try running: sudo sh -c 'echo 24 > /sys/class/gpio/unexport'")
        print("Or reboot the Raspberry Pi to reset GPIO state")
        print("To force mock mode, set environment variable: FORCE_MOCK_DISPLAY=true")
        epd7in3e = None
        
    except Exception as e:
        print(f"Warning: Unexpected error initializing display: {e}")
        print("Display functions will be mocked.")
        epd7in3e = None

class DisplayService:
    def __init__(self):
        self.config_service = ConfigService()
        self.weather_service = WeatherService()
        self.calendar_service = CalendarService()
        
        # Display dimensions
        self.COLOR_WIDTH = 800
        self.COLOR_HEIGHT = 480
        self.BW_WIDTH = 800  # These will be sent to ESP32 via I2C
        self.BW_HEIGHT = 480
        
        # Initialize color display
        self.color_epd = None
        if epd7in3e:
            try:
                self.color_epd = epd7in3e.EPD()
            except Exception as e:
                print(f"Warning: Could not initialize color display: {e}")
    
    def get_status(self) -> Dict[str, str]:
        """Get display status"""
        color_status = "active" if self.color_epd else "unavailable"
        bw_status = "active"  # Assume ESP32 connection is always available
        
        return {
            'color': color_status,
            'bw': bw_status,
            'last_color_refresh': self._get_last_refresh_time('color'),
            'last_bw_refresh': self._get_last_refresh_time('bw')
        }
    
    def _get_last_refresh_time(self, display_type: str) -> str:
        """Get last refresh time from file"""
        filename = f"last_refresh_{display_type}.txt"
        try:
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return f.read().strip()
        except:
            pass
        return "Never"
    
    def _set_last_refresh_time(self, display_type: str):
        """Set last refresh time to file"""
        filename = f"last_refresh_{display_type}.txt"
        try:
            with open(filename, 'w') as f:
                f.write(datetime.now().isoformat())
        except:
            pass
    
    def refresh_display(self, display_type: str = 'both') -> Dict[str, Any]:
        """Refresh display(s)"""
        result = {'success': True, 'messages': []}
        
        if display_type in ['color', 'both']:
            try:
                self.update_color_display()
                result['messages'].append('Color display refreshed successfully')
            except Exception as e:
                result['success'] = False
                result['messages'].append(f'Color display refresh failed: {str(e)}')
        
        if display_type in ['bw', 'both']:
            try:
                self.update_bw_display()
                result['messages'].append('B&W display refreshed successfully')
            except Exception as e:
                result['success'] = False
                result['messages'].append(f'B&W display refresh failed: {str(e)}')
        
        return result
    
    def update_color_display(self):
        """Update the color e-ink display with AI-generated image"""
        try:
            # Generate AI image based on today's events and weather
            image = self.generate_daily_image()
            
            if self.color_epd:
                # Initialize display
                self.color_epd.init()
                self.color_epd.Clear()
                
                # Display the image
                self.color_epd.display(self.color_epd.getbuffer(image))
                
                # Put display to sleep to save power
                self.color_epd.sleep()
            else:
                # Save image for testing
                image.save('color_display_output.png')
                print("Color display mocked - image saved as color_display_output.png")
            
            self._set_last_refresh_time('color')
            
        except Exception as e:
            raise Exception(f"Color display update failed: {str(e)}")
    
    def update_bw_display(self):
        """Update the B&W display via ESP32 with weather and calendar info"""
        try:
            # Create B&W display content
            image = self.create_bw_display_image()
            
            # In a real implementation, this would send data to ESP32 via I2C
            # For now, we'll save the image
            image.save('bw_display_output.png')
            print("B&W display mocked - image saved as bw_display_output.png")
            print("In production: This data would be sent to ESP32 via I2C")
            
            self._set_last_refresh_time('bw')
            
        except Exception as e:
            raise Exception(f"B&W display update failed: {str(e)}")
    
    def generate_daily_image(self) -> Image.Image:
        """Generate AI image based on calendar events and weather"""
        try:
            # Get today's data
            weather_summary = self.weather_service.get_weather_summary_for_ai()
            events = self.calendar_service.get_today_events()
            
            # Create prompt for AI
            prompt_parts = [
                "Create a beautiful, artistic image that represents today.",
                f"Weather: {weather_summary}",
            ]
            
            if events:
                event_summaries = []
                for event in events[:3]:  # Limit to 3 events
                    if event['title']:
                        event_text = event['title']
                        if event['location']:
                            event_text += f" at {event['location']}"
                        event_summaries.append(event_text)
                
                if event_summaries:
                    prompt_parts.append(f"Today's events: {', '.join(event_summaries)}")
            
            prompt_parts.append("Style: Modern, minimalist, suitable for an e-ink display with limited colors.")
            prompt_parts.append("Image should be 800x480 pixels, landscape orientation.")
            
            prompt = " ".join(prompt_parts)
            
            # Generate image with Gemini (if available)
            gemini_api_key = self.config_service.get('gemini_api_key')
            
            if gemini_api_key:
                try:
                    genai.configure(api_key=gemini_api_key)
                    model = genai.GenerativeModel('gemini-pro-vision')
                    
                    # Note: This is a placeholder - Gemini Pro Vision currently doesn't generate images
                    # In a real implementation, you'd use a different model or service for image generation
                    # For now, create a simple text-based image
                    return self._create_fallback_color_image(weather_summary, events)
                    
                except Exception as e:
                    print(f"AI image generation failed: {e}")
                    return self._create_fallback_color_image(weather_summary, events)
            else:
                return self._create_fallback_color_image(weather_summary, events)
                
        except Exception as e:
            print(f"Error generating daily image: {e}")
            return self._create_fallback_color_image("Weather unavailable", [])
    
    def _create_fallback_color_image(self, weather_summary: str, events: List[Dict]) -> Image.Image:
        """Create a fallback image when AI generation is not available"""
        # Create image with white background
        image = Image.new('RGB', (self.COLOR_WIDTH, self.COLOR_HEIGHT), 'white')
        draw = ImageDraw.Draw(image)
        
        # Try to load fonts
        try:
            title_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32)
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            title_font = text_font = small_font = ImageFont.load_default()
        
        # Draw title
        title = datetime.now().strftime("%A, %B %d, %Y")
        draw.text((50, 50), title, fill='black', font=title_font)
        
        # Draw weather
        draw.text((50, 120), "Weather:", fill='black', font=text_font)
        weather_lines = self._wrap_text(weather_summary, text_font, self.COLOR_WIDTH - 100)
        y_pos = 160
        for line in weather_lines:
            draw.text((50, y_pos), line, fill='blue', font=small_font)
            y_pos += 25
        
        # Draw events
        if events:
            y_pos += 30
            draw.text((50, y_pos), "Today's Events:", fill='black', font=text_font)
            y_pos += 40
            
            for event in events[:4]:  # Show max 4 events
                event_text = event['title']
                if event['location']:
                    event_text += f" @ {event['location']}"
                
                event_lines = self._wrap_text(event_text, small_font, self.COLOR_WIDTH - 100)
                for line in event_lines:
                    draw.text((50, y_pos), f"• {line}", fill='darkgreen', font=small_font)
                    y_pos += 25
                
                if y_pos > self.COLOR_HEIGHT - 50:
                    break
        
        return image
    
    def create_bw_display_image(self) -> Image.Image:
        """Create B&W display image with weather and calendar info"""
        # Create image with white background
        image = Image.new('1', (self.BW_WIDTH, self.BW_HEIGHT), 1)  # '1' mode for 1-bit pixels
        draw = ImageDraw.Draw(image)
        
        # Try to load fonts
        try:
            large_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
            medium_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 22)
            small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
        except:
            large_font = medium_font = small_font = ImageFont.load_default()
        
        # Get data
        try:
            weather = self.weather_service.get_current_weather()
            events = self.calendar_service.get_upcoming_events(days=3)
        except:
            weather = {'temperature': '?', 'description': 'Weather unavailable'}
            events = []
        
        # Draw weather section
        draw.text((20, 20), f"{weather.get('temperature', '?')}°C", fill=0, font=large_font)
        draw.text((20, 60), weather.get('description', 'N/A'), fill=0, font=medium_font)
        
        if 'location' in weather:
            draw.text((20, 90), weather['location'], fill=0, font=small_font)
        
        # Draw line separator
        draw.line([(20, 130), (self.BW_WIDTH - 20, 130)], fill=0, width=2)
        
        # Draw upcoming events
        draw.text((20, 150), "Upcoming Events:", fill=0, font=medium_font)
        
        y_pos = 190
        for event in events[:6]:  # Show max 6 events
            if y_pos > self.BW_HEIGHT - 40:
                break
                
            # Format event text
            event_text = event['title'][:40] + ('...' if len(event['title']) > 40 else '')
            draw.text((20, y_pos), event_text, fill=0, font=small_font)
            
            # Event time
            if event['start']:
                try:
                    event_time = event['start'].strftime("%m/%d %H:%M")
                    draw.text((20, y_pos + 20), event_time, fill=0, font=small_font)
                except:
                    pass
            
            y_pos += 50
        
        if not events:
            draw.text((20, 190), "No upcoming events", fill=0, font=small_font)
        
        return image
    
    def _wrap_text(self, text: str, font, max_width: int) -> List[str]:
        """Wrap text to fit within max_width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            try:
                if font.getsize(test_line)[0] <= max_width:
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)  # Single word too long
            except:
                # Fallback if getsize not available
                if len(test_line) * 10 <= max_width:  # Rough estimate
                    current_line.append(word)
                else:
                    if current_line:
                        lines.append(' '.join(current_line))
                        current_line = [word]
                    else:
                        lines.append(word)
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines