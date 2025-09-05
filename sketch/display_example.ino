#include <GxEPD2_BW.h>
#include <GxEPD2_3C.h>
#include <Fonts/FreeMonoBold12pt7b.h>

// Pin-Definitionen
#define EPD_CS     5
#define EPD_DC     2
#define EPD_RST    4
#define EPD_BUSY   15
#define EPD_PWR    0

GxEPD2_BW<GxEPD2_750_T7, GxEPD2_750_T7::HEIGHT> display(GxEPD2_750_T7(EPD_CS, EPD_DC, EPD_RST, EPD_BUSY));

void setup() {
  Serial.begin(115200);
  Serial.println("\n=== Waveshare 7.5\" V2 E-Paper Test ===");
  
  // Wichtig: Längere Initialisierungspause für E-Paper
  delay(1000);
  
  // Power Pin aktivieren
  if (EPD_PWR >= 0) {
    pinMode(EPD_PWR, OUTPUT);
    digitalWrite(EPD_PWR, HIGH);
    delay(500); // Längere Wartezeit für stabile Stromversorgung
    Serial.println("Power Pin aktiviert");
  }
  
  // Pin-Modi explizit setzen
  pinMode(EPD_CS, OUTPUT);
  pinMode(EPD_DC, OUTPUT);
  pinMode(EPD_RST, OUTPUT);
  pinMode(EPD_BUSY, INPUT);
  
  digitalWrite(EPD_CS, HIGH);
  digitalWrite(EPD_DC, LOW);
  digitalWrite(EPD_RST, HIGH);
  
  Serial.println("\nHardware-Einstellungen am HAT:");
  Serial.println("Display Config: B (0.47R) - für V2");
  Serial.println("Interface Config: 0 (4-line SPI) - Standard");
  
  // Pin Status prüfen
  Serial.println("\nPin-Belegung:");
  Serial.println("CS:   GPIO" + String(EPD_CS));
  Serial.println("DC:   GPIO" + String(EPD_DC));
  Serial.println("RST:  GPIO" + String(EPD_RST));
  Serial.println("BUSY: GPIO" + String(EPD_BUSY));
  if (EPD_PWR >= 0) Serial.println("PWR:  GPIO" + String(EPD_PWR));
  
  Serial.println("\nInitial BUSY Pin Status: " + String(digitalRead(EPD_BUSY)));
  
  Serial.println("\nInitialisiere Display...");
  
  try {
    // Längere Debug-Init für bessere Fehlererkennung
    display.init(115200, true, 2, false); // debug=true, reset_duration=2ms, initial_refresh=false
    Serial.println("✓ Display erfolgreich initialisiert!");
    
    // Display-Informationen
    Serial.println("\nDisplay-Informationen:");
    Serial.println("Breite: " + String(display.width()));
    Serial.println("Höhe: " + String(display.height()));
    
    // Warte bis Display bereit ist
    Serial.println("Warte auf Display-Bereitschaft...");
    int timeout = 0;
    while (digitalRead(EPD_BUSY) == LOW && timeout < 100) {
      delay(100);
      timeout++;
      Serial.print(".");
    }
    Serial.println("\nDisplay ist bereit!");
    
    // Einfacher Test
    testDisplay();
    
  } catch (...) {
    Serial.println("✗ Display-Initialisierung fehlgeschlagen!");
    Serial.println("Prüfen Sie:");
    Serial.println("- HAT Display Config: B (0.47R)");
    Serial.println("- HAT Interface Config: 0 (4-line SPI)");
    Serial.println("- Verkabelung und 3.3V Versorgung");
  }
}

void loop() {
  // Alle 10 Sekunden BUSY-Pin Status anzeigen
  Serial.println("BUSY Pin Status: " + String(digitalRead(EPD_BUSY)));
  delay(10000);
}

void testDisplay() {
  Serial.println("\nStarte Display-Test...");
  
  // Display löschen
  display.fillScreen(GxEPD_WHITE);
  
  // Text schreiben
  display.setTextColor(GxEPD_BLACK);
  display.setFont(&FreeMonoBold12pt7b);
  
  display.setCursor(50, 50);
  display.print("E-Ink Test erfolgreich!");
  
  display.setCursor(50, 100);
  display.print("Aufloesung: " + String(display.width()) + "x" + String(display.height()));
  
  display.setCursor(50, 150);
  display.print("Display-Typ funktioniert!");
  
  // Rahmen zeichnen
  display.drawRect(20, 20, display.width()-40, display.height()-40, GxEPD_BLACK);
  
  Serial.println("Aktualisiere Display (das kann 10-30 Sekunden dauern)...");
  display.display();
  Serial.println("✓ Display-Update abgeschlossen!");
}

// Zusätzliche Diagnose-Funktion
void checkPins() {
  Serial.println("\n=== Pin-Diagnose ===");
  
  // Reset-Test
  digitalWrite(EPD_RST, LOW);
  delay(10);
  digitalWrite(EPD_RST, HIGH);
  delay(10);
  Serial.println("Reset-Pin getestet");
  
  // BUSY-Pin lesen
  Serial.println("BUSY-Pin Status: " + String(digitalRead(EPD_BUSY)));
  
  // CS-Pin Test
  digitalWrite(EPD_CS, HIGH);
  delay(1);
  digitalWrite(EPD_CS, LOW);
  delay(1);
  digitalWrite(EPD_CS, HIGH);
  Serial.println("CS-Pin getestet");
}