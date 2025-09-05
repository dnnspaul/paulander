#!/usr/bin/env python3
"""
Debug script to test Waveshare library import and GPIO initialization
Run this separately from the Flask app to isolate issues
"""
import sys
import os

# Add the waveshare library path
waveshare_lib_path = os.path.join(os.path.dirname(__file__), 'waveshare-epaper/RaspberryPi_JetsonNano/python/lib')
if os.path.exists(waveshare_lib_path):
    sys.path.append(waveshare_lib_path)
    print(f"Added Waveshare library path: {waveshare_lib_path}")
else:
    print(f"Waveshare library path not found: {waveshare_lib_path}")
    sys.exit(1)

try:
    print("Testing imports...")
    print(f"Python executable: {sys.executable}")
    
    # Test required libraries
    import RPi.GPIO as GPIO
    print(f"✓ RPi.GPIO imported successfully from: {GPIO.__file__}")
    
    import spidev
    print(f"✓ spidev imported successfully from: {spidev.__file__}")
    
    import numpy
    print(f"✓ numpy imported successfully from: {numpy.__file__}")
    
    import PIL
    print(f"✓ PIL imported successfully from: {PIL.__file__}")
    
    import gpiozero
    print(f"✓ gpiozero imported successfully from: {gpiozero.__file__}")
    
    # Check for lgpio (optional, newer GPIO library)
    try:
        import lgpio
        print(f"✓ lgpio available from: {lgpio.__file__}")
    except ImportError:
        print("! lgpio not available (this is OK, will fall back to RPi.GPIO)")
    
    # Test Waveshare library import
    print("\nImporting Waveshare library...")
    from waveshare_epd import epd7in3e
    print("✓ epd7in3e imported successfully")
    
    # Test display initialization
    print("\nTesting display initialization...")
    epd = epd7in3e.EPD()
    print("✓ EPD object created successfully")
    
    epd.init()
    print("✓ Display initialized successfully")
    
    print("✓ All tests passed! The display should work in the main application.")
    
    # Clean up
    epd.sleep()
    epd7in3e.epdconfig.module_exit(cleanup=True)
    print("✓ Cleanup completed")

except ImportError as e:
    print(f"✗ Import error: {e}")
    print("Make sure all dependencies are installed:")
    print("  uv sync --extra rpi")
    
except RuntimeError as e:
    print(f"✗ GPIO/Runtime error: {e}")
    print("This might be due to:")
    print("  - GPIO permissions (try with sudo)")
    print("  - SPI not enabled (sudo raspi-config)")
    print("  - Hardware not connected properly")
    print("  - GPIO pin conflicts")
    
except Exception as e:
    print(f"✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()

print("\nDebug complete.")