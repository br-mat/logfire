#include "LogFireUDP.h"

LogFireUDPClass LogFireUDP;

static const char* LEVEL_NAMES[] = { "", "INFO", "WARN", "ERROR", "CRITICAL" };

void LogFireUDPClass::begin(const char* deviceName, const char* host, uint16_t port) {
    _deviceName = deviceName;
    _host = host;
    _port = port;
    _udp.begin(0);  // bind to any ephemeral local port
}

void LogFireUDPClass::mirrorSerial(bool enable) {
    _mirrorSerial = enable;
}

void LogFireUDPClass::localOnly(bool enable) {
    _localOnly = enable;
    // no disconnect — UDP is connectionless
}

void LogFireUDPClass::log(const char* message, uint8_t level) {
    if (_mirrorSerial) {
        if (level > 0 && level <= 4) {
            Serial.print("[");
            Serial.print(LEVEL_NAMES[level]);
            Serial.print("] ");
        }
        Serial.println(message);
    }

    if (_localOnly || WiFi.status() != WL_CONNECTED) {
        return;
    }

    String payload;
    if (level > 0) {
        payload = _deviceName + "(-" + String(level) + "): " + message;
    } else {
        payload = _deviceName + ": " + message;
    }

    _udp.beginPacket(_host.c_str(), _port);
    _udp.print(payload);
    _udp.endPacket();
}

void LogFireUDPClass::log(const String& message, uint8_t level) {
    log(message.c_str(), level);
}
