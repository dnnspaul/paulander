#include <Wire.h>
#include <GxEPD2_BW.h>
#include <GxEPD2_3C.h>
#include <Fonts/FreeMonoBold9pt7b.h>
#include <Fonts/FreeMonoBold12pt7b.h>
#include <Fonts/FreeMono9pt7b.h>
#include <ArduinoJson.h>
#include <time.h>

// Pin definitions for 7.5" B&W e-paper display
#define EPD_CS 5
#define EPD_DC 2
#define EPD_RST 4
#define EPD_BUSY 15
#define EPD_PWR 0

// I2C configuration - using working parameters from your test
#define I2C_SDA 21
#define I2C_SCL 22
#define I2C_ADDRESS 0x42  // Changed to match Python code expectations

// Display object for Waveshare 7.5" V2 B&W display (800x480)
GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

// Enhanced data structure for weather and calendar info
struct WeatherData {
  float current_temperature;
  char current_description[64];
  float today_min;
  float today_max;
  char today_description[64];
  float tomorrow_min;
  float tomorrow_max;
  char tomorrow_description[64];
  bool has_tomorrow_data;
  char location[32];
  uint32_t timestamp;
};

struct CalendarEvent {
  char title[64];
  char location[32];
  uint32_t start_time;
  bool valid;
};

struct DisplayData {
  WeatherData weather;
  CalendarEvent events[6];  // Max 6 events
  uint8_t event_count;
  uint32_t data_hash;  // Hash to detect changes
  uint32_t timestamp;
};

// Global variables
DisplayData currentData;
DisplayData previousData;
bool dataReceived = false;
bool displayNeedsUpdate = false;
bool displayInitialized = false;
unsigned long lastDisplayUpdate = 0;
const unsigned long DISPLAY_UPDATE_INTERVAL = 1800000;  // 30 minutes in ms

// I2C receive buffer - 2KB to handle complete data structure with headroom
uint8_t i2cBuffer[2048];  // 2KB buffer for reliable data reception
volatile bool i2cDataReady = false;
volatile int i2cDataLength = 0;
volatile int totalDataReceived = 0;
volatile bool receivingMultipart = false;
volatile unsigned long lastReceiveTime = 0;  // Global variable for timeout tracking

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Paulander ESP32 B&W Display Controller ===");

  // Configure timezone for Europe/Berlin (no WiFi needed, just local timezone setting)
  setenv("TZ", "CET-1CEST,M3.5.0,M10.5.0/3", 1);
  tzset();
  Serial.println("Timezone set to Europe/Berlin (CET/CEST)");

  // Debug: Print structure sizes
  Serial.printf("WeatherData size: %d bytes\n", sizeof(WeatherData));
  Serial.printf("CalendarEvent size: %d bytes\n", sizeof(CalendarEvent));
  Serial.printf("DisplayData size: %d bytes\n", sizeof(DisplayData));
  Serial.printf("Expected data from Pi: 719 bytes\n");

  // Initialize I2C first with explicit parameters (like your working test)
  Serial.println("Initializing I2C slave communication...");
  Wire.begin(I2C_ADDRESS, I2C_SDA, I2C_SCL, 100000);  // Address, SDA, SCL, Frequency
  Wire.onReceive(onI2CReceive);
  Wire.onRequest(onI2CRequest);

  Serial.printf("I2C initialized as slave at address 0x%02X\n", I2C_ADDRESS);
  Serial.printf("SDA: GPIO%d, SCL: GPIO%d\n", I2C_SDA, I2C_SCL);

  // Initialize display (but make it more robust)
  initializeDisplay();

  // Initialize data structures
  memset(&currentData, 0, sizeof(DisplayData));
  memset(&previousData, 0, sizeof(DisplayData));

  // Initialize I2C timing
  lastReceiveTime = millis();

  Serial.println("ESP32 ready for I2C communication");
  Serial.println("Waiting for data from Raspberry Pi...");

  // Show startup message only if display initialized
  if (displayInitialized) {
    showStartupMessage();
  }
}

void loop() {
  // Check for I2C data
  if (i2cDataReady) {
    processI2CData();
    i2cDataReady = false;
  }

  // Check for I2C receive timeout
  if (receivingMultipart && (millis() - lastReceiveTime > 15000)) {  // Increased to 15 seconds
    Serial.printf("I2C receive timeout - received %d bytes (expected JSON data)\n", totalDataReceived);

    // Check if we have complete JSON even though we timed out
    if (isJsonComplete()) {
      Serial.println("Data size close to expected - processing anyway");
      i2cDataLength = totalDataReceived;
      i2cDataReady = true;
    } else {
      Serial.println("Insufficient data - resetting buffer");
      // Clear the buffer completely to avoid contamination
      memset(i2cBuffer, 0, sizeof(i2cBuffer));
    }

    totalDataReceived = 0;
    receivingMultipart = false;
    lastReceiveTime = millis();
  }

  // Check if display needs update
  if (displayNeedsUpdate || (millis() - lastDisplayUpdate > DISPLAY_UPDATE_INTERVAL)) {
    if (dataReceived && displayInitialized) {
      updateDisplay();
      displayNeedsUpdate = false;
      lastDisplayUpdate = millis();
    }
  }

  // Keep alive message every 10 seconds
  static unsigned long lastKeepAlive = 0;
  if (millis() - lastKeepAlive > 10000) {
    if (receivingMultipart) {
      Serial.printf("ESP32 running... (receiving multipart: %d bytes received)\n", totalDataReceived);
    } else {
      Serial.println("ESP32 running... waiting for I2C data");
    }
    lastKeepAlive = millis();
  }

  delay(100);  // Small delay to prevent busy waiting
}

void initializeDisplay() {
  Serial.println("Initializing 7.5\" B&W e-paper display...");

  try {
    delay(1000);  // Initialization pause

    // Power pin
    if (EPD_PWR >= 0) {
      pinMode(EPD_PWR, OUTPUT);
      digitalWrite(EPD_PWR, HIGH);
      delay(500);
      Serial.println("Power pin activated");
    }

    // Set pin modes explicitly
    pinMode(EPD_CS, OUTPUT);
    pinMode(EPD_DC, OUTPUT);
    pinMode(EPD_RST, OUTPUT);
    pinMode(EPD_BUSY, INPUT);

    digitalWrite(EPD_CS, HIGH);
    digitalWrite(EPD_DC, LOW);
    digitalWrite(EPD_RST, HIGH);

    display.init(115200, true, 2, false);

    // Set rotation for portrait mode (90 degrees clockwise)
    display.setRotation(3);

    Serial.println("✓ Display initialized successfully!");
    Serial.printf("Display size: %dx%d (after rotation)\n", display.width(), display.height());

    // Wait until display is ready
    Serial.println("Waiting for display readiness...");
    int timeout = 0;
    while (digitalRead(EPD_BUSY) == LOW && timeout < 50) {
      delay(100);
      timeout++;
      Serial.print(".");
    }
    Serial.println("\nDisplay is ready!");

    displayInitialized = true;

  } catch (...) {
    Serial.println("✗ Display initialization failed!");
    Serial.println("Continuing without display (I2C will still work)");
    displayInitialized = false;
  }
}

void onI2CReceive(int length) {
  if (length > 0) {
    // If this is the first chunk of a new transmission, clear buffer
    if (totalDataReceived == 0) {
      memset(i2cBuffer, 0, sizeof(i2cBuffer));
      Serial.println("Starting new I2C transmission - buffer cleared");
    }

    // Read all available bytes
    int bytesRead = 0;
    while (Wire.available() && (totalDataReceived + bytesRead) < sizeof(i2cBuffer)) {
      i2cBuffer[totalDataReceived + bytesRead] = Wire.read();
      bytesRead++;
    }

    totalDataReceived += bytesRead;
    Serial.printf("I2C chunk received: %d bytes (total: %d)\n", bytesRead, totalDataReceived);

    // Debug: Show first few bytes of this chunk if it's the first one
    if (totalDataReceived <= 32) {
      Serial.printf("First chunk bytes: ");
      for (int i = 0; i < min(8, bytesRead); i++) {
        uint8_t byte = i2cBuffer[totalDataReceived - bytesRead + i];
        if (byte >= 32 && byte <= 126) {
          Serial.printf("'%c' ", byte);  // Show printable characters
        } else {
          Serial.printf("0x%02X ", byte);  // Show non-printable as hex
        }
      }
      Serial.println();
    }

    // Check if we have received complete JSON data
    if (isJsonComplete()) {
      Serial.printf("Complete data received: %d bytes (expected: %d)\n", totalDataReceived, sizeof(DisplayData));
      i2cDataLength = totalDataReceived;
      i2cDataReady = true;
      totalDataReceived = 0;  // Reset for next message
      receivingMultipart = false;
    } else {
      // We're in the middle of receiving a multi-part message
      receivingMultipart = true;

      // Update global timeout timer
      lastReceiveTime = millis();

      // Check for timeout in main loop
    }
  }
}

bool isJsonComplete() {
  // Check if we have received complete JSON data
  if (totalDataReceived < 20) return false;  // Minimum for basic JSON structure

  bool foundStart = false;
  int braceCount = 0;

  for (int i = 0; i < totalDataReceived; i++) {
    if (i2cBuffer[i] == 0x00) continue;  // Skip register bytes

    if (i2cBuffer[i] == '{') {
      if (!foundStart) foundStart = true;
      braceCount++;
    } else if (i2cBuffer[i] == '}' && foundStart) {
      braceCount--;
      if (braceCount == 0) {
        Serial.printf("JSON completion detected at position %d (braces balanced)\n", i);
        return true;
      }
    }
  }

  return false;
}

void onI2CRequest() {
  // Send status back to Raspberry Pi
  uint8_t status = dataReceived ? 1 : 0;
  Wire.write(status);
  Serial.printf("I2C status request - sent: %d\n", status);
}

void processI2CData() {
  Serial.printf("Processing I2C data: %d bytes\n", i2cDataLength);

  if (i2cDataLength >= 50) {  // JSON should be at least 50 bytes
    // Reconstruct JSON by removing register bytes (0x00) from chunks
    // Each 16-byte chunk starts with 0x00, so we need to clean this up
    uint8_t cleanBuffer[2048];
    int cleanLength = 0;

    Serial.println("Reconstructing JSON from I2C chunks...");
    for (int i = 0; i < i2cDataLength;) {
      if (i2cBuffer[i] == 0x00) {
        // Skip register byte
        i++;
        Serial.printf("Skipped register byte at position %d\n", i - 1);
      } else {
        // Copy data byte
        cleanBuffer[cleanLength++] = i2cBuffer[i];
        i++;
      }
    }

    // Null-terminate the JSON string
    cleanBuffer[cleanLength] = '\0';

    Serial.printf("Reconstructed JSON: %d bytes (from %d raw bytes)\n", cleanLength, i2cDataLength);

    Serial.println("=== JSON Data Debug ===");
    Serial.printf("Clean JSON length: %d bytes\n", cleanLength);
    Serial.printf("Clean JSON data: %s\n", (char*)cleanBuffer);

    // Parse JSON from clean buffer
    DynamicJsonDocument doc(2048);  // 2KB for JSON parsing
    DeserializationError error = deserializeJson(doc, (char*)cleanBuffer);

    if (error) {
      Serial.printf("✗ JSON parsing failed: %s\n", error.c_str());
      return;
    }

    Serial.println("✓ JSON parsed successfully");

    // Extract enhanced weather data
    currentData.weather.current_temperature = doc["weather"]["current_temperature"];
    strncpy(currentData.weather.current_description, doc["weather"]["current_description"] | "", sizeof(currentData.weather.current_description) - 1);
    currentData.weather.today_min = doc["weather"]["today_min"];
    currentData.weather.today_max = doc["weather"]["today_max"];
    strncpy(currentData.weather.today_description, doc["weather"]["today_description"] | "", sizeof(currentData.weather.today_description) - 1);
    
    // Check if tomorrow data is available
    if (doc["weather"]["tomorrow_min"].isNull() || doc["weather"]["tomorrow_max"].isNull()) {
      currentData.weather.has_tomorrow_data = false;
      currentData.weather.tomorrow_min = 0;
      currentData.weather.tomorrow_max = 0;
      strncpy(currentData.weather.tomorrow_description, "No forecast", sizeof(currentData.weather.tomorrow_description) - 1);
    } else {
      currentData.weather.has_tomorrow_data = true;
      currentData.weather.tomorrow_min = doc["weather"]["tomorrow_min"];
      currentData.weather.tomorrow_max = doc["weather"]["tomorrow_max"];
      strncpy(currentData.weather.tomorrow_description, doc["weather"]["tomorrow_description"] | "No forecast", sizeof(currentData.weather.tomorrow_description) - 1);
    }
    
    strncpy(currentData.weather.location, doc["weather"]["location"] | "", sizeof(currentData.weather.location) - 1);
    currentData.weather.timestamp = doc["weather"]["timestamp"];

    // Extract events data
    currentData.event_count = doc["event_count"];
    if (currentData.event_count > 6) currentData.event_count = 6;  // Safety check

    JsonArray events = doc["events"];
    for (int i = 0; i < currentData.event_count && i < 6; i++) {
      strncpy(currentData.events[i].title, events[i]["title"] | "", sizeof(currentData.events[i].title) - 1);
      strncpy(currentData.events[i].location, events[i]["location"] | "", sizeof(currentData.events[i].location) - 1);
      currentData.events[i].start_time = events[i]["start_time"];
      currentData.events[i].valid = events[i]["valid"];
    }

    currentData.timestamp = doc["timestamp"];

    // Calculate hash of current data for change detection
    uint32_t newHash = calculateDataHash(&currentData);

    Serial.println("=== JSON Data Processed Successfully ===");
    Serial.printf("Current Temperature: %.1f°C\n", currentData.weather.current_temperature);
    Serial.printf("Current Weather: %s\n", currentData.weather.current_description);
    Serial.printf("Today: %.1f-%.1f°C, %s\n", currentData.weather.today_min, currentData.weather.today_max, currentData.weather.today_description);
    if (currentData.weather.has_tomorrow_data) {
      Serial.printf("Tomorrow: %.1f-%.1f°C, %s\n", currentData.weather.tomorrow_min, currentData.weather.tomorrow_max, currentData.weather.tomorrow_description);
    } else {
      Serial.println("Tomorrow: No forecast available");
    }
    Serial.printf("Location: %s\n", currentData.weather.location);
    Serial.printf("Events: %d\n", currentData.event_count);

    // Debug calendar events
    Serial.println("=== Calendar Events ===");
    for (int i = 0; i < currentData.event_count && i < 6; i++) {
      CalendarEvent& event = currentData.events[i];
      Serial.printf("Event %d: '%s'\n", i + 1, event.title);
      Serial.printf("  Location: '%s'\n", event.location);
      Serial.printf("  Start time: %u\n", event.start_time);
      Serial.printf("  Valid: %s\n", event.valid ? "yes" : "no");

      // Convert timestamp to readable format
      if (event.start_time > 0) {
        time_t eventTime = event.start_time;
        struct tm* timeInfo = localtime(&eventTime);
        Serial.printf("  Readable time: %02d/%02d %02d:%02d\n",
                      timeInfo->tm_mon + 1, timeInfo->tm_mday,
                      timeInfo->tm_hour, timeInfo->tm_min);
      }
    }

    Serial.printf("Data hash: 0x%08X\n", newHash);

    // Check if data changed
    if (newHash != previousData.data_hash) {
      Serial.println("✓ Data changed - display update needed");
      displayNeedsUpdate = true;
      previousData = currentData;
      previousData.data_hash = newHash;
    } else {
      Serial.println("✓ Data unchanged - no display update needed");
    }

    currentData.data_hash = newHash;
    dataReceived = true;
  } else {
    Serial.printf("✗ Insufficient I2C data: %d bytes (expected: 50+ bytes for JSON)\n", i2cDataLength);
  }
}

uint32_t calculateDataHash(DisplayData* data) {
  // Simple hash calculation for change detection
  uint32_t hash = 0;
  uint8_t* ptr = (uint8_t*)data;
  for (int i = 0; i < sizeof(DisplayData) - sizeof(uint32_t); i++) {
    hash = hash * 31 + ptr[i];
  }
  return hash;
}

void showStartupMessage() {
  if (!displayInitialized) return;

  display.fillScreen(GxEPD_WHITE);
  display.setTextColor(GxEPD_BLACK);
  display.setFont(&FreeMonoBold12pt7b);

  display.setCursor(50, 80);
  display.print("Paulander Display Controller");

  display.setFont(&FreeMono9pt7b);
  display.setCursor(50, 120);
  display.print("ESP32 Controller ready");

  display.setCursor(50, 150);
  display.print("I2C Address: 0x42 (0x2A)");

  display.setCursor(50, 180);
  display.print("Waiting for data from Raspberry Pi...");

  // Draw border
  display.drawRect(20, 20, display.width() - 40, display.height() - 40, GxEPD_BLACK);

  Serial.println("Displaying startup message...");
  display.display();
  Serial.println("✓ Startup message displayed");
}

void updateDisplay() {
  if (!dataReceived || !displayInitialized) return;

  Serial.println("=== Updating B&W Display ===");

  display.fillScreen(GxEPD_WHITE);
  display.setTextColor(GxEPD_BLACK);

  // Weather section
  drawWeatherSection();

  // Calendar section
  drawCalendarSection();

  // Footer with timestamp
  drawFooter();

  Serial.println("Refreshing display (this may take 10-30 seconds)...");
  unsigned long startTime = millis();
  display.display();
  unsigned long endTime = millis();

  Serial.printf("✓ Display updated successfully in %lu ms\n", endTime - startTime);
}

void drawWeatherSection() {
  // Weather section header
  display.setFont(&FreeMonoBold12pt7b);
  display.setCursor(30, 50);
  display.print("Wetter");
  
  // Current temperature - large and prominent
  display.setFont(&FreeMonoBold12pt7b);
  display.setCursor(30, 90);
  display.print("Jetzt:");
  display.setCursor(130, 90);
  display.printf("%.1f°C", currentData.weather.current_temperature);
  
  // Current weather description
  display.setFont(&FreeMono9pt7b);
  display.setCursor(30, 115);
  display.print(currentData.weather.current_description);
  
  // Today's min/max temperatures
  display.setFont(&FreeMonoBold9pt7b);
  display.setCursor(30, 145);
  display.print("Heute:");
  display.setCursor(100, 145);
  display.printf("%.0f-%.0f°C", currentData.weather.today_min, currentData.weather.today_max);
  
  // Tomorrow's forecast (if available)
  if (currentData.weather.has_tomorrow_data) {
    display.setCursor(30, 170);
    display.print("Morgen:");
    display.setCursor(100, 170);
    display.printf("%.0f-%.0f°C", currentData.weather.tomorrow_min, currentData.weather.tomorrow_max);
  }
  
  // Location (if available)
  if (strlen(currentData.weather.location) > 0) {
    display.setFont(&FreeMono9pt7b);
    display.setCursor(30, 195);
    display.print(currentData.weather.location);
  }
  
  // Separator line
  display.drawLine(20, 220, display.width()-20, 220, GxEPD_BLACK);
}

void drawCalendarSection() {
  display.setFont(&FreeMonoBold9pt7b);
  display.setCursor(30, 260);
  display.print("Termine:");
  
  int yPos = 290;
  display.setFont(&FreeMono9pt7b);
  
  if (currentData.event_count == 0) {
    display.setCursor(30, yPos);
    display.print("Keine Termine");
    return;
  }
  
  for (int i = 0; i < currentData.event_count && i < 8; i++) {  // Increased to 8 events for portrait
    if (yPos > display.height() - 80) break;  // More space in portrait mode
    
    CalendarEvent& event = currentData.events[i];
    if (!event.valid) continue;
    
    // Event title (adjust for narrower width in portrait)
    String eventTitle = String(event.title);
    if (eventTitle.length() > 28) {  // Reduced for narrower display
      eventTitle = eventTitle.substring(0, 25) + "...";
    }
    
    display.setCursor(30, yPos);
    display.print("• " + eventTitle);
    yPos += 25;
    
    // Event time and location
    if (event.start_time > 0) {
      time_t eventTime = event.start_time;
      struct tm* timeInfo = localtime(&eventTime);
      
      display.setCursor(40, yPos);
      display.printf("%02d.%02d %02d:%02d", 
                    timeInfo->tm_mon + 1, timeInfo->tm_mday,
                    timeInfo->tm_hour, timeInfo->tm_min);
      
      // Location on separate line if it exists
      if (strlen(event.location) > 0) {
        yPos += 20;
        display.setCursor(40, yPos);
        String loc = String(event.location);
        if (loc.length() > 35) {
          loc = loc.substring(0, 32) + "...";
        }
        display.printf("@ %s", loc.c_str());
      }
      yPos += 25;
    }
    
    yPos += 10;  // Gap between events
  }
}

void drawFooter() {
  if (!displayInitialized) return;
  
  // Draw bottom border
  display.drawLine(20, display.height()-50, display.width()-20, display.height()-50, GxEPD_BLACK);
  
  // Last update timestamp - centered in portrait
  display.setFont(&FreeMono9pt7b);
  display.setCursor(30, display.height()-25);
  
  time_t now = currentData.timestamp;
  struct tm* timeInfo = localtime(&now);
  display.printf("Aktualisiert: %02d:%02d", timeInfo->tm_hour, timeInfo->tm_min);
  
  // ESP32 status - positioned for narrower display
  display.setCursor(display.width()-30, display.height()-25);
  display.print("<3");
}