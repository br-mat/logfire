/**
 * LogFire PlatformIO Example
 *
 * Connects to WiFi and sends a log message every 5 seconds.
 * Edit WIFI_SSID, WIFI_PASS, and LOGFIRE_HOST below.
 */

#if defined(USE_ESP32)
  #include <WiFi.h>
#elif defined(USE_ESP8266)
  #include <ESP8266WiFi.h>
#endif

#include <LogFire.h>

const char* WIFI_SSID = "YOUR_SSID";
const char* WIFI_PASS = "YOUR_PASSWORD";
const char* LOGFIRE_HOST = "10.0.0.XX";
const uint16_t LOGFIRE_PORT = 1880;

unsigned long lastLog = 0;
int counter = 0;

void setup() {
    Serial.begin(115200);

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("Connecting to WiFi");
    while (WiFi.status() != WL_CONNECTED) {
        delay(500);
        Serial.print(".");
    }
    Serial.println(" connected!");

    LogFire.begin("ESPLog", LOGFIRE_HOST, LOGFIRE_PORT);
    LogFire.log("Device booted");  // level 0 (plain) by default
}

void loop() {
    if (millis() - lastLog >= 5000) {
        lastLog = millis();
        counter++;
        uint8_t lvl = counter % 5;  // cycle through 0-4
        LogFire.log("Heartbeat #" + String(counter), lvl);
    }
}
