#ifndef LOGFIRE_UDP_H
#define LOGFIRE_UDP_H

#include <Arduino.h>

#ifdef ESP32
  #include <WiFi.h>
  #include <WiFiUdp.h>
#elif defined(ESP8266)
  #include <ESP8266WiFi.h>
  #include <WiFiUdp.h>
#endif

class LogFireUDPClass {
public:
    void begin(const char* deviceName, const char* host, uint16_t port = 1880);
    void log(const char* message, uint8_t level = 0);
    void log(const String& message, uint8_t level = 0);
    void mirrorSerial(bool enable);
    void localOnly(bool enable);

private:
    String _deviceName;
    String _host;
    uint16_t _port = 1880;
    bool _mirrorSerial = true;
    bool _localOnly = false;
    WiFiUDP _udp;
};

extern LogFireUDPClass LogFireUDP;

#endif
