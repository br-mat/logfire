#ifndef LOGFIRE_H
#define LOGFIRE_H

#include <Arduino.h>

class LogFireClass {
public:
    void begin(const char* deviceName, const char* host, uint16_t port = 1880);
    void log(const char* message, uint8_t level = 0);
    void log(const String& message, uint8_t level = 0);

private:
    String _deviceName;
    String _url;
};

extern LogFireClass LogFire;

#endif
