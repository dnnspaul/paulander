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

// I2C configuration
#define I2C_SDA    21
#define I2C_SCL    22
#define I2C_ADDRESS 0x42  // ESP32 I2C slave address

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
unsigned long lastDisplayUpdate = 0;
const unsigned long DISPLAY_UPDATE_INTERVAL = 1800000; // 30 minutes in ms

// I2C receive buffer
uint8_t i2cBuffer[512];
volatile bool i2cDataReady = false;
volatile int i2cDataLength = 0;

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Paulander ESP32 B&W Display Controller ===");
  
  // Initialize display
  initializeDisplay();
  
  // Initialize I2C as slave
  initializeI2C();
  
  // Initialize data structures
  memset(&currentData, 0, sizeof(DisplayData));
  memset(&previousData, 0, sizeof(DisplayData));
  
  Serial.println("ESP32 ready for I2C communication");
  Serial.println("Waiting for data from Raspberry Pi...");
  
  // Show startup message
  showStartupMessage();
}

void loop() {
  // Check for I2C data
  if (i2cDataReady) {
    processI2CData();
    i2cDataReady = false;
  }
  
  // Check if display needs update
  if (displayNeedsUpdate || (millis() - lastDisplayUpdate > DISPLAY_UPDATE_INTERVAL)) {
    if (dataReceived) {
      updateDisplay();
      displayNeedsUpdate = false;
      lastDisplayUpdate = millis();
    }
  }
  
  delay(100);  // Small delay to prevent busy waiting
}

void initializeDisplay() {
  Serial.println("Initializing 7.5\" B&W e-paper display...");
  
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
  
  try {
    display.init(115200, true, 2, false);
    Serial.println("✓ Display initialized successfully!");
    Serial.printf("Display size: %dx%d\n", display.width(), display.height());
    
    // Wait until display is ready
    Serial.println("Waiting for display readiness...");
    int timeout = 0;
    while (digitalRead(EPD_BUSY) == LOW && timeout < 100) {
      delay(100);
      timeout++;
      Serial.print(".");
    }
    Serial.println("\nDisplay is ready!");
    
  } catch (...) {
    Serial.println("✗ Display initialization failed!");
  }
}

void initializeI2C() {
  Serial.println("Initializing I2C slave communication...");
  
  Wire.begin(I2C_ADDRESS, I2C_SDA, I2C_SCL);
  Wire.onReceive(onI2CReceive);
  Wire.onRequest(onI2CRequest);
  
  Serial.printf("I2C initialized as slave at address 0x%02X\n", I2C_ADDRESS);
  Serial.printf("SDA: GPIO%d, SCL: GPIO%d\n", I2C_SDA, I2C_SCL);
}

void onI2CReceive(int length) {
  if (length > 0 && length <= sizeof(i2cBuffer)) {
    i2cDataLength = 0;
    while (Wire.available() && i2cDataLength < sizeof(i2cBuffer)) {
      i2cBuffer[i2cDataLength++] = Wire.read();
    }
    i2cDataReady = true;
    
    Serial.printf("I2C data received: %d bytes\n", i2cDataLength);
  }
}

void onI2CRequest() {
  // Send status back to Raspberry Pi
  uint8_t status = dataReceived ? 1 : 0;
  Wire.write(status);
}

void processI2CData() {
  if (i2cDataLength >= sizeof(DisplayData)) {
    // Copy received data
    memcpy(&currentData, i2cBuffer, sizeof(DisplayData));
    
    // Calculate hash of current data for change detection
    uint32_t newHash = calculateDataHash(&currentData);
    
    Serial.println("=== I2C Data Processed ===");
    Serial.printf("Temperature: %.1f°C\n", currentData.weather.temperature);
    Serial.printf("Weather: %s\n", currentData.weather.description);
    Serial.printf("Location: %s\n", currentData.weather.location);
    Serial.printf("Events: %d\n", currentData.event_count);
    Serial.printf("Data hash: 0x%08X\n", newHash);
    
    // Check if data changed
    if (newHash != previousData.data_hash) {
      Serial.println("Data changed - display update needed");
      displayNeedsUpdate = true;
      previousData = currentData;
      previousData.data_hash = newHash;
    } else {
      Serial.println("Data unchanged - no display update needed");
    }
    
    currentData.data_hash = newHash;
    dataReceived = true;
  } else {
    Serial.printf("Invalid I2C data length: %d (expected: %d)\n", i2cDataLength, sizeof(DisplayData));
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
  display.fillScreen(GxEPD_WHITE);
  display.setTextColor(GxEPD_BLACK);
  display.setFont(&FreeMonoBold12pt7b);
  
  display.setCursor(50, 80);
  display.print("Paulander B&W Display");
  
  display.setFont(&FreeMono9pt7b);
  display.setCursor(50, 120);
  display.print("ESP32 Controller Ready");
  
  display.setCursor(50, 150);
  display.print("Waiting for data from RPi...");
  
  // Draw border
  display.drawRect(20, 20, display.width()-40, display.height()-40, GxEPD_BLACK);
  
  Serial.println("Displaying startup message...");
  display.display();
  Serial.println("✓ Startup message displayed");
}

void updateDisplay() {
  if (!dataReceived) return;
  
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

// Debug function to print data
void printReceivedData() {
  Serial.println("=== Received Data ===");
  Serial.printf("Weather: %.1f°C, %s\n", currentData.weather.temperature, currentData.weather.description);
  Serial.printf("Location: %s\n", currentData.weather.location);
  Serial.printf("Events (%d):\n", currentData.event_count);
  
  for (int i = 0; i < currentData.event_count; i++) {
    if (currentData.events[i].valid) {
      Serial.printf("  %d: %s\n", i+1, currentData.events[i].title);
      if (strlen(currentData.events[i].location) > 0) {
        Serial.printf("     @ %s\n", currentData.events[i].location);
      }
    }
  }
}