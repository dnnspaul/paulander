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
2. Configure your iCloud calendar credentials
3. Set your OpenWeather API key
4. Optionally configure Gemini API key for AI-generated images

## Hardware Requirements

- Raspberry Pi Zero 2 WH
- Waveshare 7.3" color e-ink display (800x480)
- ESP32 NodeMCU CP2102 (for B&W display)
- Waveshare 7.5" black and white e-ink display (800x480)

## Features

- **Calendar Integration**: Connects to iCloud calendar via CalDAV
- **Weather Display**: Current weather and forecast from OpenWeatherMap
- **Dual Displays**: 
  - Color display: Daily AI-generated image refresh at 6 AM
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

For detailed hardware setup and configuration, see CLAUDE.md.

## Production Deployment

For production use on Raspberry Pi, set `FLASK_ENV=production` in your `.env` file to disable debug mode and auto-reload, which can interfere with GPIO hardware initialization.