#include "LogFire.h"

#ifdef ESP32
  #include <WiFi.h>
  #include <HTTPClient.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <ESP8266HTTPClient.h>
  #include <WiFiClient.h>
#endif

LogFireClass LogFire;

void LogFireClass::begin(const char* deviceName, const char* host, uint16_t port) {
    _deviceName = deviceName;
    _url = "http://" + String(host) + ":" + String(port) + "/log";
}

void LogFireClass::log(const char* message, uint8_t level) {
    if (WiFi.status() != WL_CONNECTED) return;

    HTTPClient http;
    WiFiClient client;

    #ifdef ESP32
      http.begin(_url);
    #else
      http.begin(client, _url);
    #endif

    http.setTimeout(1000);
    http.addHeader("Content-Type", "text/plain");

    String body;
    if (level > 0) {
        body = _deviceName + "(-" + String(level) + "): " + message;
    } else {
        body = _deviceName + ": " + message;
    }
    http.POST(body);
    http.end();
}

void LogFireClass::log(const String& message, uint8_t level) {
    log(message.c_str(), level);
}
