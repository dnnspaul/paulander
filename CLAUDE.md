# Paulander
## General
Paulander is a flask app running on a Raspberry Pi Zero 2 W connected to an e-ink display (color display).
To the raspberry pi is also a ESP32 NodeMCU connected via I2C. Checkout the PINOUT.md file for the exact pins.
The ESP32 is connected to another e-ink display (black and white display).

The color display is used to show a daily AI-generated image (from Gemini)based on a prompt that includes the todays calendar events and the weather.
The black and white display is used to show the weather and upcomingcalendar events.

Paulander is supposed to be running at my girlfriends flat, so everything needs to be running very robust with automatic restarts in case of crashes.

## Hardware
- Raspberry Pi Zero 2 WH [Amazon](https://amzn.to/3V2a7Xa)
- ESP32 NodeMCU CP2102 [Amazon](https://amzn.to/3Vmwp6d)
- Display 1: [Waveshare 7.5" black and white e-ink display (800x480](https://amzn.to/41QK9cH))
- Display 2: [Waveshare 7.3" color e-ink display (800x480)](https://www.amazon.de/dp/B0D9K193FY)

## Hardware Documentation
- Black and white display: E-Ink Python Example: https://raw.githubusercontent.com/waveshareteam/e-Paper/refs/heads/master/RaspberryPi_JetsonNano/python/lib/waveshare_epd/epd7in5_V2.py
- Black and white display: E-Ink Documentation: https://www.waveshare.com/wiki/7.5inch_e-Paper_HAT_Manual#Working_With_Raspberry_Pi
- Color display: E-Ink Python Example: https://github.com/waveshareteam/e-Paper/blob/master/RaspberryPi_JetsonNano/python/examples/epd_7in3e_test.py
- Color display: E-Ink Documentation: https://www.waveshare.com/wiki/7.3inch_e-Paper_HAT_(E)_Manual#Working_With_Raspberry_Pi

## Software
Paulander is a flask app serving a small web app to the end-user to setup the calendar authentication and set the weather location.
The flask app serves the backend that will be used by VueJS in the frontend. The backend also handles the connection to the e-ink display and the I2C data transfer to the ESP32.
The frontend is using TailwindCSS and VueJS. It's built for mobile first and should be responsive.
The application should be started by `uv`.

### Calendar
To load the calendar data, we use the CalDAV protocol. The user needs to create an app-specific password for the iCloud account
and put it into the web interface along with the apple id.

### Weather
The weather data is fetched from the OpenWeatherMap API. The user can set the location in the web interface.

### Deployment and Testing
The application will run bare-metal on the Raspberry Pi. DON'T START THE APP ON THE DEVELOPMENT MACHINE. I WILL COMMIT AND PUSH TO GITHUB AND THEN PULL IT TO THE RASPBERRY PI.

### Black and white display
The display is fully refreshed every 30 minutes. Check out the linked documentation for finding out the best way to send the data to the display. The display is connected via SPI to the ESP32 and the ESP32 is connected via I2C to the Raspberry Pi. The Raspberry Pi connects to the iCloud and OpenWeatherMap API to get the data and sends it to the ESP32. The ESP32 then renders the data and sends it to the display.

There is an example sketch in the sketch folder that shows how to send the data to the display.

### Color display
The display is refreshed every 24 hours at 06:00 in the morning. For now use an example image or generate one, we will care about that later.
I added the git submodule `github.com/waveshareteam/e-Paper` to the project. It contains the examples and the library for the display. Use `epd_7in3e_test.py` as a starting point.