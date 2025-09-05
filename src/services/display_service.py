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
from src.services.config_service import ConfigService
from src.services.weather_service import WeatherService
from src.services.calendar_service import CalendarService

# Add the waveshare library path from git submodule
waveshare_lib_path = os.path.join(os.path.dirname(__file__), '../../waveshare-epaper/RaspberryPi_JetsonNano/python/lib')
sys.path.append(waveshare_lib_path)

# Check if we should force mock mode (useful for development)
FORCE_MOCK_DISPLAY = os.getenv('FORCE_MOCK_DISPLAY', 'false').lower() == 'true'

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
            from waveshare_epd import epd7in3e as _epd7in3e
            epd7in3e = _epd7in3e
            print("Successfully imported epd7in3e module")
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
        """Apply Floyd-Steinberg dithering for e-ink display with 6 colors"""
        # Define the 6 colors supported by the e-ink display (RGB values)
        eink_colors = [
            (0, 0, 0),       # Black
            (255, 255, 255), # White
            (255, 0, 0),     # Red
            (0, 255, 0),     # Green
            (0, 0, 255),     # Blue
            (255, 255, 0),   # Yellow
        ]
        
        # Convert image to RGB if not already
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Convert to numpy array for easier manipulation
        img_array = np.array(image, dtype=np.float32)
        height, width = img_array.shape[:2]
        
        # Apply Floyd-Steinberg dithering
        for y in range(height):
            for x in range(width):
                old_pixel = img_array[y, x].copy()
                
                # Find the closest color from the e-ink palette
                new_pixel = self._find_closest_color(old_pixel, eink_colors)
                img_array[y, x] = new_pixel
                
                # Calculate quantization error
                quant_error = old_pixel - new_pixel
                
                # Distribute error to neighboring pixels using Floyd-Steinberg weights
                if x + 1 < width:
                    img_array[y, x + 1] += quant_error * 7/16
                if y + 1 < height:
                    if x - 1 >= 0:
                        img_array[y + 1, x - 1] += quant_error * 3/16
                    img_array[y + 1, x] += quant_error * 5/16
                    if x + 1 < width:
                        img_array[y + 1, x + 1] += quant_error * 1/16
        
        # Clamp values to valid range and convert back to PIL Image
        img_array = np.clip(img_array, 0, 255).astype(np.uint8)
        return Image.fromarray(img_array, 'RGB')
    
    def _find_closest_color(self, pixel: np.ndarray, color_palette: List[tuple]) -> np.ndarray:
        """Find the closest color in the palette using Euclidean distance"""
        min_distance = float('inf')
        closest_color = color_palette[0]
        
        for color in color_palette:
            # Calculate Euclidean distance in RGB space
            distance = np.sqrt(np.sum((pixel - np.array(color)) ** 2))
            if distance < min_distance:
                min_distance = distance
                closest_color = color
        
        return np.array(closest_color, dtype=np.float32)
    
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
            events = self.calendar_service.get_upcoming_events(days_ahead=3)
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