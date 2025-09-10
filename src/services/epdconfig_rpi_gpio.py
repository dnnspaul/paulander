# Custom epdconfig implementation using RPi.GPIO instead of gpiozero
# This resolves "LED is closed or uninitialized" errors

import os
import logging
import sys
import time
import subprocess

try:
    import RPi.GPIO as GPIO
    import spidev
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False

logger = logging.getLogger(__name__)

# Pin definition (module level for compatibility)
RST_PIN  = 17
DC_PIN   = 25
CS_PIN   = 8
BUSY_PIN = 24
PWR_PIN  = 18
MOSI_PIN = 10
SCLK_PIN = 11

class RaspberryPi:
    # Pin definition
    RST_PIN  = 17
    DC_PIN   = 25
    CS_PIN   = 8
    BUSY_PIN = 24
    PWR_PIN  = 18
    MOSI_PIN = 10
    SCLK_PIN = 11

    def __init__(self):
        if not GPIO_AVAILABLE:
            raise ImportError("RPi.GPIO and spidev are required for display hardware")
        
        self.SPI = spidev.SpiDev()
        
        # Initialize GPIO
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.RST_PIN, GPIO.OUT)
        GPIO.setup(self.DC_PIN, GPIO.OUT)
        GPIO.setup(self.CS_PIN, GPIO.OUT)  # Add CS pin
        GPIO.setup(self.PWR_PIN, GPIO.OUT)
        GPIO.setup(self.BUSY_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        
        print("GPIO pins initialized with RPi.GPIO")

    def digital_write(self, pin, value):
        if pin == self.RST_PIN:
            GPIO.output(self.RST_PIN, GPIO.HIGH if value else GPIO.LOW)
        elif pin == self.DC_PIN:
            GPIO.output(self.DC_PIN, GPIO.HIGH if value else GPIO.LOW)
        elif pin == self.CS_PIN:
            GPIO.output(self.CS_PIN, GPIO.HIGH if value else GPIO.LOW)
        elif pin == self.PWR_PIN:
            GPIO.output(self.PWR_PIN, GPIO.HIGH if value else GPIO.LOW)

    def digital_read(self, pin):
        if pin == self.BUSY_PIN:
            return GPIO.input(self.BUSY_PIN)
        elif pin == self.RST_PIN:
            return GPIO.input(self.RST_PIN)
        elif pin == self.DC_PIN:
            return GPIO.input(self.DC_PIN)
        elif pin == self.CS_PIN:
            return GPIO.input(self.CS_PIN)
        elif pin == self.PWR_PIN:
            return GPIO.input(self.PWR_PIN)

    def delay_ms(self, delaytime):
        time.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        self.SPI.writebytes(data)

    def spi_writebyte2(self, data):
        self.SPI.writebytes2(data)

    def module_init(self, cleanup=False):
        # Ensure GPIO mode is set (in case it was reset by cleanup)
        GPIO.setmode(GPIO.BCM)
        
        # Power on the display
        GPIO.output(self.PWR_PIN, GPIO.HIGH)
        
        if not cleanup:
            # SPI device, bus = 0, device = 0
            try:
                self.SPI.open(0, 0)
                self.SPI.max_speed_hz = 4000000
                self.SPI.mode = 0b00
                print("SPI initialized successfully")
            except Exception as e:
                print(f"SPI initialization failed: {e}")
                return -1
        return 0

    def module_exit(self, cleanup=False):
        logger.debug("spi end")
        try:
            self.SPI.close()
        except:
            pass

        # Turn off all pins
        GPIO.output(self.RST_PIN, GPIO.LOW)
        GPIO.output(self.DC_PIN, GPIO.LOW)
        GPIO.output(self.CS_PIN, GPIO.LOW)
        GPIO.output(self.PWR_PIN, GPIO.LOW)
        logger.debug("close 5V, Module enters 0 power consumption ...")
        
        if cleanup:
            GPIO.cleanup()
            print("GPIO cleanup completed")

# Global implementation instance
implementation = None

def module_init(cleanup=False):
    global implementation
    if implementation is None:
        implementation = RaspberryPi()
    return implementation.module_init(cleanup)

def module_exit(cleanup=False):
    global implementation
    if implementation:
        implementation.module_exit(cleanup)

def digital_write(pin, value):
    global implementation
    if implementation:
        implementation.digital_write(pin, value)

def digital_read(pin):
    global implementation
    if implementation:
        return implementation.digital_read(pin)
    return 0

def delay_ms(delaytime):
    time.sleep(delaytime / 1000.0)

def spi_writebyte(data):
    global implementation
    if implementation:
        implementation.spi_writebyte(data)

def spi_writebyte2(data):
    global implementation
    if implementation:
        implementation.spi_writebyte2(data)