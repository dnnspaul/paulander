import os
import sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from datetime import datetime
from typing import Dict, Any, List
from io import BytesIO
import google.generativeai as genai
from google import genai as genai_new
from google.genai import types
import struct
import time
from src.services.config_service import ConfigService
from src.services.weather_service import WeatherService
from src.services.calendar_service import CalendarService

# Add the waveshare library path from git submodule
waveshare_lib_path = os.path.join(os.path.dirname(__file__), '../../waveshare-epaper/RaspberryPi_JetsonNano/python/lib')
sys.path.append(waveshare_lib_path)

# Check if we should force mock mode (useful for development)
FORCE_MOCK_DISPLAY = os.getenv('FORCE_MOCK_DISPLAY', 'false').lower() == 'true'

# I2C configuration
ESP32_I2C_ADDRESS = 0x42
I2C_BUS = 1  # RPi I2C bus number

# Try to import I2C libraries
try:
    import smbus2
    I2C_AVAILABLE = True
except ImportError:
    I2C_AVAILABLE = False

# Global variables for lazy loading
epd7in3e = None
_epd7in3e_loaded = False
_epd7in3e_error = None

def _load_epd7in3e():
    """Lazy load the epd7in3e module to avoid GPIO conflicts at import time"""
    global epd7in3e, _epd7in3e_loaded, _epd7in3e_error
    
    if _epd7in3e_loaded:
        return epd7in3e
    
    if FORCE_MOCK_DISPLAY:
        print("FORCE_MOCK_DISPLAY is enabled - display functions will be mocked")
        epd7in3e = None
    else:
        try:
            # Import our custom RPi.GPIO-based epdconfig first
            from src.services import epdconfig_rpi_gpio
            
            # Import the waveshare module
            from waveshare_epd import epd7in3e as _epd7in3e
            
            # Monkey patch the epdconfig to use our RPi.GPIO implementation
            _epd7in3e.epdconfig = epdconfig_rpi_gpio
            
            epd7in3e = _epd7in3e
            print("Successfully imported epd7in3e module with RPi.GPIO patch")
            print(f"Patched epdconfig module: {epd7in3e.epdconfig.__name__}")
        except ImportError as e:
            print(f"Warning: Waveshare e-paper library not available: {e}")
            print("Display functions will be mocked.")
            epd7in3e = None
            _epd7in3e_error = e
        except Exception as e:
            print(f"Warning: Error importing display module: {e}")
            print("Display functions will be mocked.")
            epd7in3e = None
            _epd7in3e_error = e
    
    _epd7in3e_loaded = True
    return epd7in3e

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
        
        # Initialize color display (lazy loaded)
        self.color_epd = None
        self.display_initialized = False
        
        # I2C communication
        self.i2c_bus = None
        self.i2c_initialized = False
        
        # Data caching for B&W display
        self.cached_weather_data = None
        self.cached_calendar_data = None
        self.last_api_fetch = 0
        self.last_i2c_send = 0
        self.API_CACHE_DURATION = 1800  # 30 minutes in seconds
        self.I2C_SEND_INTERVAL = 30     # 30 seconds
        
        # Don't load the display module during init - wait until actually needed
        print("Display service initialized (hardware will be loaded on first use)")
    
    def _ensure_display_loaded(self):
        """Ensure the display hardware is loaded and initialized"""
        if self.color_epd is not None:
            return  # Already loaded
        
        # Lazy load the waveshare module
        epd_module = _load_epd7in3e()
        
        if epd_module:
            try:
                print("Lazy loading display hardware...")
                self.color_epd = epd_module.EPD()
                print("✓ Color display hardware loaded successfully")
            except Exception as e:
                print(f"✗ Warning: Could not initialize color display: {e}")
                print("This may be due to GPIO conflicts or hardware issues")
                self.color_epd = None
        else:
            print("✗ Waveshare module not available, display functions will be mocked")
            self.color_epd = None
    
    def _ensure_i2c_initialized(self):
        """Ensure I2C bus is initialized for ESP32 communication"""
        if self.i2c_initialized:
            return True
        
        if not I2C_AVAILABLE:
            print("✗ smbus2 not available, I2C communication will be mocked")
            return False
        
        if FORCE_MOCK_DISPLAY:
            print("✗ FORCE_MOCK_DISPLAY enabled, I2C communication will be mocked")
            return False
        
        try:
            self.i2c_bus = smbus2.SMBus(I2C_BUS)
            self.i2c_initialized = True
            print(f"✓ I2C bus {I2C_BUS} initialized for ESP32 communication")
            return True
        except Exception as e:
            print(f"✗ Failed to initialize I2C: {e}")
            return False

    def get_status(self) -> Dict[str, str]:
        """Get display status"""
        # Try to lazy load display if not already loaded
        if not self.color_epd:
            self._ensure_display_loaded()
        
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
            print("=== Starting color display update ===")
            
            # Generate AI image based on today's events and weather
            print("Generating AI image...")
            image = self.generate_daily_image()
            print(f"✓ Image generated: {image.size[0]}x{image.size[1]} pixels, mode: {image.mode}")
            
            # Ensure display is loaded before using it
            if not self.color_epd:
                self._ensure_display_loaded()
            
            if self.color_epd:
                print("Hardware display detected, initializing...")
                
                # Get the epd module for cleanup operations
                epd_module = _load_epd7in3e()
                
                try:
                    # Initialize display with proper error handling
                    if not self.display_initialized:
                        print("First time initialization, cleaning up any previous state...")
                        try:
                            if epd_module:
                                epd_module.epdconfig.module_exit(cleanup=True)
                        except:
                            pass
                        
                    print("Initializing display hardware...")
                    print(f"Using epdconfig: {epd_module.epdconfig.__name__}")
                    self.color_epd.init()
                    self.display_initialized = True
                    print("✓ Display initialized")
                    
                    print("Clearing display...")
                    self.color_epd.Clear()
                    print("✓ Display cleared")
                    
                    # Display the image
                    print("Converting image to display buffer...")
                    buffer = self.color_epd.getbuffer(image)
                    print(f"✓ Buffer created, size: {len(buffer) if buffer else 'None'} bytes")
                    
                    print("Sending image to display...")
                    self.color_epd.display(buffer)
                    print("✓ Image sent to display")
                    
                    # Put display to sleep to save power
                    print("Putting display to sleep...")
                    self.color_epd.sleep()
                    print("✓ Display in sleep mode")
                    
                    print("✓ Color display updated successfully")
                    
                except Exception as gpio_error:
                    print(f"✗ GPIO/Display error: {gpio_error}")
                    
                    # Try to recover by reinitializing the entire display
                    print("Attempting display recovery...")
                    try:
                        # Clean up completely
                        if epd_module:
                            epd_module.epdconfig.module_exit(cleanup=True)
                        
                        # Reinitialize the display object
                        self.color_epd = epd_module.EPD() if epd_module else None
                        self.display_initialized = False
                        
                        if self.color_epd:
                            # Try initialization again
                            self.color_epd.init()
                            self.display_initialized = True
                            print("✓ Display recovery successful")
                            
                            # Now try the display operation again
                            self.color_epd.Clear()
                            buffer = self.color_epd.getbuffer(image)
                            self.color_epd.display(buffer)
                            self.color_epd.sleep()
                            print("✓ Color display updated successfully after recovery")
                        else:
                            raise Exception("Could not reinitialize display")
                        
                    except Exception as recovery_error:
                        print(f"✗ Display recovery failed: {recovery_error}")
                        # Save image as fallback
                        filename = 'color_display_output_gpio_error.png'
                        image.save(filename)
                        print(f"✓ Image saved as {filename} due to GPIO error")
                        raise Exception(f"Display hardware error: {gpio_error}")
            else:
                # Save image for testing
                filename = 'color_display_output.png'
                image.save(filename)
                print(f"✓ Color display mocked - image saved as {filename}")
                print(f"  Image details: {image.size[0]}x{image.size[1]} pixels, {image.mode} mode")
            
            self._set_last_refresh_time('color')
            print("✓ Last refresh time updated")
            print("=== Color display update completed ===")
            
        except Exception as e:
            print(f"✗ Color display update failed: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"Color display update failed: {str(e)}")
    
    def update_bw_display(self):
        """Update the B&W display via ESP32 with weather and calendar info"""
        try:
            print("=== Starting B&W display update ===")
            
            # Check if we need to fetch fresh data from APIs (every 30 minutes)
            current_time = time.time()
            if (current_time - self.last_api_fetch) >= self.API_CACHE_DURATION:
                print("Fetching fresh data from APIs...")
                self._fetch_and_cache_data()
                self.last_api_fetch = current_time
            else:
                print("Using cached data (API cache still valid)")
            
            # Send data to ESP32 via I2C (every 30 seconds)
            if (current_time - self.last_i2c_send) >= self.I2C_SEND_INTERVAL:
                print("Sending data to ESP32 via I2C...")
                self._send_data_to_esp32()
                self.last_i2c_send = current_time
            else:
                print("I2C send interval not reached yet")
            
            self._set_last_refresh_time('bw')
            print("✓ B&W display update completed")
            
        except Exception as e:
            print(f"✗ B&W display update failed: {e}")
            raise Exception(f"B&W display update failed: {str(e)}")
    
    def _fetch_and_cache_data(self):
        """Fetch fresh weather and calendar data from APIs and cache it"""
        try:
            # Fetch weather data
            print("Fetching weather data...")
            weather = self.weather_service.get_current_weather()
            self.cached_weather_data = {
                'temperature': weather.get('temperature', 0.0),
                'description': weather.get('description', 'N/A')[:63],  # Limit to 63 chars
                'location': weather.get('location', '')[:31],  # Limit to 31 chars
                'timestamp': int(time.time())
            }
            print(f"✓ Weather cached: {self.cached_weather_data['temperature']}°C, {self.cached_weather_data['description']}")
            
            # Fetch calendar data
            print("Fetching calendar events...")
            events = self.calendar_service.get_upcoming_events(days_ahead=3)
            self.cached_calendar_data = []
            
            for i, event in enumerate(events[:6]):  # Limit to 6 events
                # Safely handle start time
                start_time = 0
                if event.get('start') and hasattr(event['start'], 'timestamp'):
                    try:
                        start_time = int(event['start'].timestamp())
                    except (AttributeError, TypeError):
                        start_time = 0
                
                event_data = {
                    'title': event.get('title', '')[:63],  # Limit to 63 chars
                    'location': event.get('location', '')[:31],  # Limit to 31 chars
                    'start_time': start_time,
                    'valid': bool(event.get('title'))
                }
                self.cached_calendar_data.append(event_data)
            
            print(f"✓ Calendar cached: {len(self.cached_calendar_data)} events")
            
        except Exception as e:
            print(f"✗ Error fetching API data: {e}")
            # Use fallback data if APIs fail
            if not self.cached_weather_data:
                self.cached_weather_data = {
                    'temperature': 0.0,
                    'description': 'Weather unavailable',
                    'location': '',
                    'timestamp': int(time.time())
                }
            if not self.cached_calendar_data:
                self.cached_calendar_data = []
    
    def _send_data_to_esp32(self):
        """Send cached weather and calendar data to ESP32 via I2C"""
        if not self.cached_weather_data:
            print("✗ No cached weather data to send")
            return
        
        # Initialize I2C if needed
        if not self._ensure_i2c_initialized():
            print("✗ I2C not available, saving mock data instead")
            self._create_mock_bw_display()
            return
        
        try:
            # Prepare data structure matching ESP32 expectations
            data = self._prepare_esp32_data()
            
            # Send data via I2C
            print(f"Sending {len(data)} bytes to ESP32 at address 0x{ESP32_I2C_ADDRESS:02X}")
            
            # Send data in chunks if needed (I2C has buffer limitations)
            chunk_size = 32  # Common I2C buffer size
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i+chunk_size]
                self.i2c_bus.write_i2c_block_data(ESP32_I2C_ADDRESS, i, chunk)
                time.sleep(0.01)  # Small delay between chunks
            
            # Read ESP32 status
            try:
                status = self.i2c_bus.read_byte(ESP32_I2C_ADDRESS)
                print(f"✓ ESP32 status: {'Data received' if status == 1 else 'Waiting for data'}")
            except:
                print("✓ Data sent (status read failed)")
            
        except Exception as e:
            print(f"✗ I2C communication failed: {e}")
            print("Falling back to mock display")
            self._create_mock_bw_display()
    
    def _prepare_esp32_data(self):
        """Prepare data structure for ESP32 communication with proper alignment"""
        # The ESP32 expects 740 bytes due to structure padding, let's match that
        data = bytearray(740)  # Pre-allocate to exact ESP32 size
        offset = 0
        
        print(f"Preparing data for ESP32 (target size: 740 bytes)")
        print(f"Weather: {self.cached_weather_data['temperature']}°C, {self.cached_weather_data['description']}")
        
        # Weather data structure (should be 104 bytes, but may be padded to 108 due to alignment)
        # float temperature (4 bytes)
        struct.pack_into('<f', data, offset, float(self.cached_weather_data['temperature']))
        offset += 4
        
        # char description[64] (64 bytes)
        desc_bytes = self.cached_weather_data['description'].encode('utf-8')[:63]
        data[offset:offset+64] = desc_bytes.ljust(64, b'\x00')
        offset += 64
        
        # char location[32] (32 bytes)
        loc_bytes = self.cached_weather_data['location'].encode('utf-8')[:31]  
        data[offset:offset+32] = loc_bytes.ljust(32, b'\x00')
        offset += 32
        
        # uint32_t timestamp (4 bytes)
        struct.pack_into('<I', data, offset, self.cached_weather_data['timestamp'])
        offset += 4
        
        # Add padding to align to 4-byte boundary if needed
        while offset % 4 != 0:
            offset += 1
        
        weather_end = offset
        print(f"Weather data ends at offset: {weather_end}")
        
        # Calendar events - each should be 101 bytes, but may be padded
        for i in range(6):
            event_start = offset
            
            if i < len(self.cached_calendar_data):
                event = self.cached_calendar_data[i]
                
                # char title[64] (64 bytes)
                title_bytes = event['title'].encode('utf-8')[:63]
                data[offset:offset+64] = title_bytes.ljust(64, b'\x00')
                offset += 64
                
                # char location[32] (32 bytes)
                event_loc_bytes = event['location'].encode('utf-8')[:31]
                data[offset:offset+32] = event_loc_bytes.ljust(32, b'\x00')
                offset += 32
                
                # uint32_t start_time (4 bytes)
                struct.pack_into('<I', data, offset, event['start_time'])
                offset += 4
                
                # bool valid (1 byte)
                struct.pack_into('B', data, offset, 1 if event['valid'] else 0)
                offset += 1
            else:
                # Empty event slot - fill with zeros
                data[offset:offset+101] = b'\x00' * 101
                offset += 101
            
            # Add padding to align each event structure to 4-byte boundary
            while (offset - event_start) % 4 != 0:
                offset += 1
        
        events_end = offset
        print(f"Events data ends at offset: {events_end}")
        
        # uint8_t event_count (1 byte)
        event_count = min(len(self.cached_calendar_data), 6)
        struct.pack_into('B', data, offset, event_count)
        offset += 1
        
        # Add padding before uint32_t fields
        while offset % 4 != 0:
            offset += 1
        
        # uint32_t data_hash (4 bytes) - will be calculated by ESP32
        struct.pack_into('<I', data, offset, 0)
        offset += 4
        
        # uint32_t timestamp (4 bytes)
        struct.pack_into('<I', data, offset, int(time.time()))
        offset += 4
        
        print(f"Final data size: {len(data)} bytes, used: {offset} bytes")
        print(f"Temperature packed: {struct.unpack('<f', data[0:4])[0]:.1f}°C")
        print(f"Description: {data[4:68].rstrip(b'\\x00').decode('utf-8', errors='ignore')}")
        
        return data
    
    def _create_mock_bw_display(self):
        """Create mock B&W display output when I2C is not available"""
        try:
            if not self.cached_weather_data:
                print("✗ No cached data for mock display")
                return
            
            image = self.create_bw_display_image()
            image.save('bw_display_output.png')
            print("✓ B&W display mocked - image saved as bw_display_output.png")
            
        except Exception as e:
            print(f"✗ Mock display creation failed: {e}")
    
    def generate_daily_image(self) -> Image.Image:
        """Generate AI image based on calendar events and weather"""
        try:
            print("=== Starting daily image generation ===")
            
            # Get today's data
            print("Fetching weather data...")
            weather_summary = self.weather_service.get_weather_summary_for_ai()
            print(f"✓ Weather summary: {weather_summary}")
            
            print("Fetching calendar events...")
            events = self.calendar_service.get_today_events()
            print(f"✓ Found {len(events)} events for today")
            
            # Generate image with Gemini (if available)
            gemini_api_key = self.config_service.get('gemini_api_key')
            
            if gemini_api_key:
                print("✓ Gemini API key found, attempting AI image generation...")
                try:
                    result = self._generate_gemini_image(weather_summary, events)
                    print("✓ AI image generation completed successfully")
                    return result
                except Exception as e:
                    print(f"✗ AI image generation failed: {e}")
                    print("Falling back to text-based image...")
                    return self._create_fallback_color_image(weather_summary, events)
            else:
                print("✗ No Gemini API key configured, using fallback image...")
                return self._create_fallback_color_image(weather_summary, events)
                
        except Exception as e:
            print(f"✗ Error generating daily image: {e}")
            print("Using emergency fallback image...")
            return self._create_fallback_color_image("Weather unavailable", [])
    
    def _generate_gemini_image(self, weather_summary: str, events: List[Dict]) -> Image.Image:
        """Generate image using Gemini API with two-step process"""
        gemini_api_key = self.config_service.get('gemini_api_key')
        print(f"Starting Gemini image generation process...")
        print(f"Weather summary: {weather_summary}")
        print(f"Events count: {len(events)}")
        
        # Step 1: Generate detailed prompt using Gemini 2.5 Flash
        prompt_generation_text = self._create_prompt_generation_request(weather_summary, events)
        print(f"Step 1: Generating detailed prompt with Gemini 2.5 Flash...")
        
        try:
            # Configure the new Gemini client
            client = genai_new.Client(api_key=gemini_api_key)
            print(f"Gemini client configured successfully")
            
            # Generate the detailed prompt
            print(f"Calling Gemini 2.5 Flash for prompt generation...")
            prompt_response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[prompt_generation_text],
            )
            
            detailed_prompt = prompt_response.text.strip()
            print(f"✓ Step 1 completed - Generated prompt: {detailed_prompt}")
            
            # Step 2: Generate image using the detailed prompt
            print(f"Step 2: Generating image with Gemini 2.5 Flash Image Preview...")
            print(f"Using prompt: {detailed_prompt[:100]}...")
            
            image_response = client.models.generate_content(
                model="gemini-2.5-flash-image-preview",
                contents=[detailed_prompt]
            )
            
            print(f"✓ Gemini API call completed, processing response...")
            print(f"Response object type: {type(image_response)}")
            print(f"Response candidates count: {len(image_response.candidates) if hasattr(image_response, 'candidates') else 'No candidates'}")
            
            if hasattr(image_response, 'candidates') and image_response.candidates:
                candidate = image_response.candidates[0]
                print(f"First candidate content parts count: {len(candidate.content.parts) if hasattr(candidate.content, 'parts') else 'No parts'}")
                
                # Extract and process the generated image
                for i, part in enumerate(candidate.content.parts):
                    print(f"Processing part {i+1}: type={type(part)}")
                    if hasattr(part, 'inline_data') and part.inline_data is not None:
                        print(f"✓ Found inline image data in part {i+1}")
                        print(f"Image data size: {len(part.inline_data.data)} bytes")
                        print(f"Image mime type: {getattr(part.inline_data, 'mime_type', 'unknown')}")
                        
                        try:
                            image = Image.open(BytesIO(part.inline_data.data))
                            print(f"✓ Image loaded successfully: {image.size[0]}x{image.size[1]} pixels, mode: {image.mode}")
                            
                            # Resize and crop to fit 800x480 display
                            print(f"Resizing and cropping image to {self.COLOR_WIDTH}x{self.COLOR_HEIGHT}...")
                            resized_image = self._resize_and_crop_image(image, self.COLOR_WIDTH, self.COLOR_HEIGHT)
                            print(f"✓ Image resized successfully")
                            
                            # Apply Floyd-Steinberg dithering for e-ink display
                            print(f"Applying Floyd-Steinberg dithering...")
                            dithered_image = self._apply_floyd_steinberg_dithering(resized_image)
                            print(f"✓ Dithering completed successfully")
                            
                            # Save debug copy
                            dithered_image.save('debug_generated_image.png')
                            print(f"✓ Debug image saved as debug_generated_image.png")
                            
                            return dithered_image
                            
                        except Exception as img_error:
                            print(f"✗ Error processing image data: {img_error}")
                            continue
                    else:
                        print(f"Part {i+1} has no inline_data or inline_data is None")
                        if hasattr(part, 'text'):
                            print(f"Part {i+1} contains text: {part.text[:100]}...")
            else:
                print(f"✗ No candidates found in response")
            
            # If no image was generated, fall back to text-based image
            print("✗ No image generated from Gemini API, using fallback")
            return self._create_fallback_color_image(weather_summary, events)
            
        except Exception as e:
            print(f"✗ Gemini image generation error: {e}")
            print(f"Exception type: {type(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return self._create_fallback_color_image(weather_summary, events)
    
    def _create_prompt_generation_request(self, weather_summary: str, events: List[Dict]) -> str:
        """Create the prompt generation request for Gemini"""
        # Get today's date
        today_date = datetime.now().strftime("%Y-%m-%d")
        
        # Format calendar events
        event_texts = []
        if events:
            for event in events[:3]:  # Limit to 3 events
                if event['title']:
                    event_text = event['title']
                    if event['location']:
                        event_text += f" ({event['location']})"
                    # Add time if available
                    if event.get('start'):
                        try:
                            time_str = event['start'].strftime("%I%p").lower()
                            event_text += f" {time_str}"
                        except:
                            pass
                    event_texts.append(event_text)
        
        events_text = "\n".join([f"- {event}" for event in event_texts]) if event_texts else "- No events scheduled"
        
        # Create the prompt generation request
        prompt_request = f"""I want you to write a detailed prompt for an AI to generate a modern painting that is being shown on an 7.3" e-ink display that supports 6 colors (black, white, red, green, blue, yellow) with a resolution of 800x480. The generated image should reflect today.

*Todays information*
Date: {today_date}
Weather: {weather_summary}
Calendar events:
{events_text}

ONLY RETURN YOUR PROMPT SUGGESTION, WITHOUT ANYTHING ELSE (DISMISS SOMETHING LIKE `Here's your prompt`).
**Never** mention the e-ink display, because it will result in an e-ink display being rendered. Also make sure, that an artistic painting is generated instead of anything that looks like an info screen.
Just in case you want to make separate images, make columns instead of rows - so split it vertically.

Make it vintage-poster style. Let it only generate an image without any title, date or something like that on the image."""
        
        return prompt_request
    
    def _resize_and_crop_image(self, image: Image.Image, target_width: int, target_height: int) -> Image.Image:
        """Resize and crop image to fit target dimensions, cropping from center"""
        # Calculate the aspect ratios
        original_width, original_height = image.size
        target_ratio = target_width / target_height
        original_ratio = original_width / original_height
        
        if original_ratio > target_ratio:
            # Image is wider than target, crop width from center
            new_height = original_height
            new_width = int(original_height * target_ratio)
            left = (original_width - new_width) // 2
            top = 0
            right = left + new_width
            bottom = original_height
        else:
            # Image is taller than target, crop height from center
            new_width = original_width
            new_height = int(original_width / target_ratio)
            left = 0
            top = (original_height - new_height) // 2
            right = original_width
            bottom = top + new_height
        
        # Crop the image from center
        cropped_image = image.crop((left, top, right, bottom))
        
        # Resize to exact target dimensions
        final_image = cropped_image.resize((target_width, target_height), Image.Resampling.LANCZOS)
        
        return final_image
    
    def _apply_floyd_steinberg_dithering(self, image: Image.Image) -> Image.Image:
        """Apply highly optimized vectorized Floyd-Steinberg dithering for e-ink display"""
        import time
        start_time = time.time()
        
        # Define the 6 colors supported by the e-ink display (RGB values)
        eink_colors = np.array([
            [0, 0, 0],       # Black
            [255, 255, 255], # White
            [255, 0, 0],     # Red
            [0, 255, 0],     # Green
            [0, 0, 255],     # Blue
            [255, 255, 0],   # Yellow
        ], dtype=np.float32)
        
        # Pre-compute Floyd-Steinberg weights as constants
        WEIGHT_RIGHT = 7.0 / 16.0      # 0.4375
        WEIGHT_BOTTOM_LEFT = 3.0 / 16.0 # 0.1875  
        WEIGHT_BOTTOM = 5.0 / 16.0      # 0.3125
        WEIGHT_BOTTOM_RIGHT = 1.0 / 16.0 # 0.0625
        
        # Convert image to RGB if not already
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array for easier manipulation
        img_array = np.array(image, dtype=np.float32)
        height, width = img_array.shape[:2]
        
        print(f"Starting vectorized Floyd-Steinberg dithering on {width}x{height} image...")
        
        # Highly optimized Floyd-Steinberg dithering
        # Process row by row to maintain error propagation order
        for y in range(height):
            # Process entire row pixels for closest color finding (vectorized)
            row_pixels = img_array[y].reshape(-1, 3)  # Shape: (width, 3)
            
            # Vectorized distance calculation for entire row
            # Broadcasting: (width, 1, 3) - (1, 6, 3) -> (width, 6, 3) -> (width, 6)
            pixel_distances = np.sum((row_pixels[:, np.newaxis, :] - eink_colors[np.newaxis, :, :]) ** 2, axis=2)
            closest_indices = np.argmin(pixel_distances, axis=1)
            new_row_pixels = eink_colors[closest_indices]
            
            # Calculate quantization errors for entire row
            row_errors = row_pixels - new_row_pixels
            
            # Process each pixel in the row for error distribution
            for x in range(width):
                # Update current pixel
                img_array[y, x] = new_row_pixels[x]
                
                # Get quantization error for current pixel
                quant_error = row_errors[x]
                
                # Optimized error distribution with pre-computed weights
                # Right pixel (x+1, y)
                if x + 1 < width:
                    img_array[y, x + 1] += quant_error * WEIGHT_RIGHT
                
                # Bottom row pixels (only if next row exists)
                if y + 1 < height:
                    # Bottom-left (x-1, y+1)
                    if x > 0:
                        img_array[y + 1, x - 1] += quant_error * WEIGHT_BOTTOM_LEFT
                    
                    # Bottom (x, y+1)
                    img_array[y + 1, x] += quant_error * WEIGHT_BOTTOM
                    
                    # Bottom-right (x+1, y+1)
                    if x + 1 < width:
                        img_array[y + 1, x + 1] += quant_error * WEIGHT_BOTTOM_RIGHT
        
        # Clamp values to valid range and convert back to PIL Image
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        
        end_time = time.time()
        print(f"✓ Vectorized dithering completed in {end_time - start_time:.2f} seconds")
        
        return Image.fromarray(img_array, 'RGB')
    
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
        
        # Apply Floyd-Steinberg dithering to fallback image as well
        return self._apply_floyd_steinberg_dithering(image)
    
    def create_bw_display_image(self) -> Image.Image:
        """Create B&W display image with weather and calendar info using cached data"""
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
        
        # Use cached data if available, otherwise fetch fresh data
        if self.cached_weather_data:
            weather = self.cached_weather_data
        else:
            try:
                weather_raw = self.weather_service.get_current_weather()
                weather = {
                    'temperature': weather_raw.get('temperature', '?'),
                    'description': weather_raw.get('description', 'N/A'),
                    'location': weather_raw.get('location', '')
                }
            except:
                weather = {'temperature': '?', 'description': 'Weather unavailable', 'location': ''}
        
        if self.cached_calendar_data:
            events = self.cached_calendar_data
        else:
            try:
                events_raw = self.calendar_service.get_upcoming_events(days_ahead=3)
                events = []
                for event in events_raw[:6]:
                    # Safely handle start time
                    start_time = 0
                    if event.get('start') and hasattr(event['start'], 'timestamp'):
                        try:
                            start_time = int(event['start'].timestamp())
                        except (AttributeError, TypeError):
                            start_time = 0
                    
                    events.append({
                        'title': event.get('title', ''),
                        'location': event.get('location', ''),
                        'start_time': start_time,
                        'valid': bool(event.get('title'))
                    })
            except:
                events = []
        
        # Draw weather section
        temp_str = f"{weather.get('temperature', '?')}"
        if isinstance(weather.get('temperature'), (int, float)):
            temp_str = f"{weather['temperature']:.1f}"
        draw.text((20, 20), f"{temp_str}°C", fill=0, font=large_font)
        draw.text((20, 60), weather.get('description', 'N/A'), fill=0, font=medium_font)
        
        if weather.get('location'):
            draw.text((20, 90), weather['location'], fill=0, font=small_font)
        
        # Draw line separator
        draw.line([(20, 130), (self.BW_WIDTH - 20, 130)], fill=0, width=2)
        
        # Draw upcoming events
        draw.text((20, 150), "Upcoming Events:", fill=0, font=medium_font)
        
        y_pos = 190
        valid_events = [e for e in events if e.get('valid', True)]
        
        for event in valid_events[:6]:  # Show max 6 events
            if y_pos > self.BW_HEIGHT - 40:
                break
                
            # Format event text
            event_title = event.get('title', '')
            event_text = event_title[:40] + ('...' if len(event_title) > 40 else '')
            draw.text((20, y_pos), event_text, fill=0, font=small_font)
            
            # Event time and location
            if event.get('start_time', 0) > 0:
                try:
                    event_time = datetime.fromtimestamp(event['start_time'])
                    time_str = event_time.strftime("%m/%d %H:%M")
                    
                    location_str = ""
                    if event.get('location'):
                        location_str = f" @ {event['location']}"
                    
                    draw.text((20, y_pos + 20), f"{time_str}{location_str}", fill=0, font=small_font)
                except:
                    pass
            
            y_pos += 50
        
        if not valid_events:
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
    
    def cleanup(self):
        """Clean up GPIO resources"""
        try:
            epd_module = _load_epd7in3e()
            if epd_module:
                epd_module.epdconfig.module_exit(cleanup=True)
                self.display_initialized = False
                print("Display GPIO cleanup completed")
        except Exception as e:
            print(f"Error during cleanup: {e}")