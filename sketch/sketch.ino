#include <Wire.h>
#include <GxEPD2_BW.h>
#include <GxEPD2_3C.h>
#include <Fonts/FreeMonoBold9pt7b.h>
#include <Fonts/FreeMonoBold12pt7b.h>
#include <Fonts/FreeMono9pt7b.h>

// Pin definitions for 7.5" B&W e-paper display
#define EPD_CS     5
#define EPD_DC     2
#define EPD_RST    4
#define EPD_BUSY   15
#define EPD_PWR    0

// I2C configuration - using working parameters from your test
#define I2C_SDA    21
#define I2C_SCL    22
#define I2C_ADDRESS 0x42  // Changed to match Python code expectations

// Display object for Waveshare 7.5" V2 B&W display (800x480)
GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

// Data structure for weather and calendar info
struct WeatherData {
  float temperature;
  char description[64];
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
const unsigned long DISPLAY_UPDATE_INTERVAL = 1800000; // 30 minutes in ms

// I2C receive buffer - larger to handle complete data structure
uint8_t i2cBuffer[800];  // Increased size to handle 719+ bytes
volatile bool i2cDataReady = false;
volatile int i2cDataLength = 0;
volatile int totalDataReceived = 0;
volatile bool receivingMultipart = false;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Paulander ESP32 B&W Display Controller ===");
  
  // Debug: Print structure sizes
  Serial.printf("WeatherData size: %d bytes\n", sizeof(WeatherData));
  Serial.printf("CalendarEvent size: %d bytes\n", sizeof(CalendarEvent));
  Serial.printf("DisplayData size: %d bytes\n", sizeof(DisplayData));
  Serial.printf("Expected data from Pi: 719 bytes\n");
  
  // Initialize I2C first with explicit parameters (like your working test)
  Serial.println("Initializing I2C slave communication...");
  Wire.begin(I2C_ADDRESS, I2C_SDA, I2C_SCL, 100000); // Address, SDA, SCL, Frequency
  Wire.onReceive(onI2CReceive);
  Wire.onRequest(onI2CRequest);
  
  Serial.printf("I2C initialized as slave at address 0x%02X\n", I2C_ADDRESS);
  Serial.printf("SDA: GPIO%d, SCL: GPIO%d\n", I2C_SDA, I2C_SCL);
  
  // Initialize display (but make it more robust)
  initializeDisplay();
  
  // Initialize data structures
  memset(&currentData, 0, sizeof(DisplayData));
  memset(&previousData, 0, sizeof(DisplayData));
  
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
  static unsigned long lastReceiveTime = millis();
  if (receivingMultipart && (millis() - lastReceiveTime > 10000)) {  // Increased to 10 seconds
    Serial.printf("I2C receive timeout - received %d bytes (expected: %d)\n", totalDataReceived, sizeof(DisplayData));
    
    // If we received close to expected amount, try to process it
    if (totalDataReceived >= 690) {  // More flexible - accept 698 bytes
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
      Serial.printf("ESP32 running... (receiving multipart: %d/%d bytes)\n", totalDataReceived, sizeof(DisplayData));
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
    Serial.println("✓ Display initialized successfully!");
    Serial.printf("Display size: %dx%d\n", display.width(), display.height());
    
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
        Serial.printf("0x%02X ", i2cBuffer[totalDataReceived - bytesRead + i]);
      }
      Serial.println();
    }
    
    // Check if we have received enough data
    // Accept data if we received the expected amount (740 bytes)
    if (totalDataReceived >= 740) {
      Serial.printf("Complete data received: %d bytes (expected: %d)\n", totalDataReceived, sizeof(DisplayData));
      i2cDataLength = totalDataReceived;
      i2cDataReady = true;
      totalDataReceived = 0;  // Reset for next message
      receivingMultipart = false;
    } else {
      // We're in the middle of receiving a multi-part message
      receivingMultipart = true;
      
      // Set timeout to reset if we don't get more data within 3 seconds
      static unsigned long lastReceiveTime = millis();
      lastReceiveTime = millis();
      
      // Check for timeout in main loop
    }
  }
}

void onI2CRequest() {
  // Send status back to Raspberry Pi
  uint8_t status = dataReceived ? 1 : 0;
  Wire.write(status);
  Serial.printf("I2C status request - sent: %d\n", status);
}

void processI2CData() {
  Serial.printf("Processing I2C data: %d bytes (DisplayData size: %d)\n", i2cDataLength, sizeof(DisplayData));
  
  if (i2cDataLength >= 690) {  // Accept data close to 698-740 bytes
    // Check if data starts with register byte 0xFF and skip it
    uint8_t* dataStart = i2cBuffer;
    int actualDataLength = i2cDataLength;
    
    if (i2cBuffer[0] == 0xFF) {
      Serial.println("Detected register byte 0xFF, skipping to actual data");
      dataStart = &i2cBuffer[1];  // Skip register byte
      actualDataLength -= 1;
    }
    
    // Debug: Show raw data at key offsets
    Serial.println("=== Raw Data Debug ===");
    Serial.printf("Data starts at offset: %d\n", (dataStart - i2cBuffer));
    Serial.printf("Bytes 0-3 (temp): 0x%02X 0x%02X 0x%02X 0x%02X\n", 
                  dataStart[0], dataStart[1], dataStart[2], dataStart[3]);
    Serial.printf("Bytes 4-10 (desc): ");
    for (int i = 4; i < 11; i++) {
      Serial.printf("0x%02X ", dataStart[i]);
    }
    Serial.println();
    
    // Show as float for temperature
    float* temp_ptr = (float*)&dataStart[0];
    Serial.printf("Temperature as float: %.2f\n", *temp_ptr);
    
    // Show description string
    Serial.printf("Description string: '");
    for (int i = 4; i < 68 && i < actualDataLength; i++) {
      if (dataStart[i] >= 32 && dataStart[i] <= 126) {
        Serial.printf("%c", dataStart[i]);
      } else if (dataStart[i] == 0) {
        break;
      }
    }
    Serial.println("'");
    
    // Copy received data (skip register byte if present)
    memcpy(&currentData, dataStart, min((int)sizeof(DisplayData), actualDataLength));
    
    // Calculate hash of current data for change detection
    uint32_t newHash = calculateDataHash(&currentData);
    
    Serial.println("=== I2C Data Processed Successfully ===");
    Serial.printf("Temperature: %.1f°C\n", currentData.weather.temperature);
    Serial.printf("Weather: %s\n", currentData.weather.description);
    Serial.printf("Location: %s\n", currentData.weather.location);
    Serial.printf("Events: %d\n", currentData.event_count);
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
    Serial.printf("✗ Insufficient I2C data: %d bytes (expected: %d)\n", i2cDataLength, sizeof(DisplayData));
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
  display.print("Paulander B&W Display");
  
  display.setFont(&FreeMono9pt7b);
  display.setCursor(50, 120);
  display.print("ESP32 Controller Ready");
  
  display.setCursor(50, 150);
  display.print("I2C Address: 0x42");
  
  display.setCursor(50, 180);
  display.print("Waiting for data from RPi...");
  
  // Draw border
  display.drawRect(20, 20, display.width()-40, display.height()-40, GxEPD_BLACK);
  
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
  // Large temperature
  display.setFont(&FreeMonoBold12pt7b);
  display.setCursor(30, 60);
  display.printf("%.1f°C", currentData.weather.temperature);
  
  // Weather description
  display.setFont(&FreeMono9pt7b);
  display.setCursor(30, 90);
  display.print(currentData.weather.description);
  
  // Location
  if (strlen(currentData.weather.location) > 0) {
    display.setCursor(30, 115);
    display.print(currentData.weather.location);
  }
  
  // Separator line
  display.drawLine(20, 140, display.width()-20, 140, GxEPD_BLACK);
}

void drawCalendarSection() {
  display.setFont(&FreeMonoBold9pt7b);
  display.setCursor(30, 170);
  display.print("Upcoming Events:");
  
  int yPos = 200;
  display.setFont(&FreeMono9pt7b);
  
  if (currentData.event_count == 0) {
    display.setCursor(30, yPos);
    display.print("No upcoming events");
    return;
  }
  
  for (int i = 0; i < currentData.event_count && i < 6; i++) {
    if (yPos > display.height() - 60) break;  // Don't overflow display
    
    CalendarEvent& event = currentData.events[i];
    if (!event.valid) continue;
    
    // Event title (truncate if too long)
    String eventTitle = String(event.title);
    if (eventTitle.length() > 35) {
      eventTitle = eventTitle.substring(0, 32) + "...";
    }
    
    display.setCursor(30, yPos);
    display.print("• " + eventTitle);
    yPos += 20;
    
    // Event time and location
    if (event.start_time > 0) {
      time_t eventTime = event.start_time;
      struct tm* timeInfo = localtime(&eventTime);
      
      display.setCursor(40, yPos);
      display.printf("%02d/%02d %02d:%02d", 
                    timeInfo->tm_mon + 1, timeInfo->tm_mday,
                    timeInfo->tm_hour, timeInfo->tm_min);
      
      if (strlen(event.location) > 0) {
        display.printf(" @ %s", event.location);
      }
      yPos += 20;
    }
    
    yPos += 5;  // Small gap between events
  }
}

void drawFooter() {
  if (!displayInitialized) return;
  
  // Draw bottom border
  display.drawLine(20, display.height()-40, display.width()-20, display.height()-40, GxEPD_BLACK);
  
  // Last update timestamp
  display.setFont(&FreeMono9pt7b);
  display.setCursor(30, display.height()-15);
  
  time_t now = currentData.timestamp;
  struct tm* timeInfo = localtime(&now);
  display.printf("Last update: %02d:%02d", timeInfo->tm_hour, timeInfo->tm_min);
  
  // ESP32 status
  display.setCursor(display.width()-150, display.height()-15);
  display.print("ESP32 OK");
}