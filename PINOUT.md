# Pinout
## Color Display
Name: Waveshare 7.3" e-Paper HAT (E)

The display is connected via SPI to the raspberry pi.

VCC -> 3.3V
GND -> GND
DIN -> PIN 19 (GPIO 10)
SCLK -> PIN 23 (GPIO 11)
CS -> PIN 24 (GPIO 8)
DC -> PIN 22 (GPIO 25)
RST -> PIN 11 (GPIO 17)
BUSY -> PIN 18 (GPIO 24)

## Black and white display
Name: Waveshare 7.5" e-Paper HAT

The display is connected via SPI to the ESP32 and the ESP32 is connected via I2C to the Raspberry Pi.

VCC -> 3.3V
GND -> GND
DIN -> GPIO23
SCLK -> GPIO18
CS -> GPIO5
DC -> GPIO2
RST -> GPIO4
BUSY -> GPIO15
PWR -> GPIO0