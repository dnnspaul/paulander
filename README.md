# Paulander

E-ink display dashboard for Raspberry Pi with calendar and weather integration.

## Quick Start

### System Dependencies (Raspberry Pi)
First install the required system packages:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-pil python3-numpy
sudo raspi-config nonint do_spi 0  # Enable SPI interface
```

### Using uv (recommended)
```bash
# Initialize git submodules (required for Waveshare e-paper library)
git submodule update --init --recursive

# Install dependencies (including Raspberry Pi GPIO support)
uv sync --extra rpi

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys

# Run the application
uv run python run.py
```

### Using pip
```bash
# Initialize git submodules (required for Waveshare e-paper library)
git submodule update --init --recursive

# Install dependencies (including Raspberry Pi GPIO support)
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your API keys

# Run the application
python run.py
```

## Configuration

1. Open http://localhost:5000/config in your browser
2. Configure your iCloud calendar credentials (required)
3. Set your OpenWeather API key (required)
4. Configure Gemini API key for AI-generated images (optional)
   - Get your API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
   - If not configured, the color display will show a text-based fallback image

## Hardware Requirements

- Raspberry Pi Zero 2 WH
- Waveshare 7.3" color e-ink display (800x480)
- ESP32 NodeMCU CP2102 (for B&W display)
- Waveshare 7.5" black and white e-ink display (800x480)

## Features

- **Calendar Integration**: Connects to iCloud calendar via CalDAV
- **Weather Display**: Current weather and forecast from OpenWeatherMap
- **AI Image Generation**: Uses Gemini 2.5 Flash to create personalized vintage-style images based on weather and calendar events, optimized with Floyd-Steinberg dithering for e-ink displays
- **Dual Displays**: 
  - Color display: Daily AI-generated vintage poster refresh at 6 AM (800x480, 6 colors)
  - B&W display: Weather and calendar updates every 30 minutes
- **Web Interface**: Mobile-first responsive configuration interface
- **Robust Operation**: Automatic restarts and error handling

## API Endpoints

- `GET /api/weather` - Current weather
- `GET /api/weather/forecast` - Weather forecast
- `GET /api/calendar/events` - Upcoming calendar events
- `POST /api/calendar/test` - Test calendar connection
- `GET /api/config` - Get configuration
- `POST /api/config` - Update configuration
- `POST /api/display/refresh` - Manually refresh displays
- `GET /api/display/status` - Display status
- `POST /api/display/test-ai-image` - Test AI image generation with dithering
- `POST /api/display/test-dithering` - Test Floyd-Steinberg dithering algorithm  
- `POST /api/display/debug-gemini` - Debug Gemini API connection and configuration
- `POST /api/display/test-hardware` - Test display hardware with simple image

For detailed hardware setup and configuration, see CLAUDE.md.

## Production Deployment

For production use on Raspberry Pi, set `FLASK_ENV=production` in your `.env` file to disable debug mode and auto-reload, which can interfere with GPIO hardware initialization.