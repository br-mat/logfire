#include "LogFire.h"

LogFireClass LogFire;

static const char* LEVEL_NAMES[] = { "", "INFO", "WARN", "ERROR", "CRITICAL" };

void LogFireClass::begin(const char* deviceName, const char* host, uint16_t port) {
    _deviceName = deviceName;
    _host = host;
    _port = port;
}

void LogFireClass::mirrorSerial(bool enable) {
    _mirrorSerial = enable;
}

void LogFireClass::localOnly(bool enable) {
    _localOnly = enable;
    if (enable) _disconnect();
}

String LogFireClass::_buildUrl() {
    return "http://" + _host + ":" + String(_port) + "/log";
}

void LogFireClass::_ensureConnected() {
    if (!_connected) {
        String url = _buildUrl();
        #ifdef ESP32
          _http.begin(url);
        #else
          _http.begin(_wifiClient, url);
        #endif
        _http.setTimeout(1000);               // response timeout
        #ifdef ESP32
          _http.setConnectTimeout(1000);      // ESP32 default is 5000 ms
        #endif
        _http.addHeader("Content-Type", "text/plain");
        _http.setReuse(true);
        _connected = true;
    }
}

void LogFireClass::_disconnect() {
    if (_connected) {
        _http.end();
        _connected = false;
    }
}

void LogFireClass::log(const char* message, uint8_t level) {
    if (_mirrorSerial) {
        if (level > 0 && level <= 4) {
            Serial.print("[");
            Serial.print(LEVEL_NAMES[level]);
            Serial.print("] ");
        }
        Serial.println(message);
    }

    if (_localOnly || WiFi.status() != WL_CONNECTED) {
        _disconnect();
        return;
    }

    String body;
    if (level > 0) {
        body = _deviceName + "(-" + String(level) + "): " + message;
    } else {
        body = _deviceName + ": " + message;
    }

    // A reused connection may have been closed by the hub: reconnect and retry
    // once. A failing fresh connection is not retried. Individual socket
    // timeouts are not an overall deadline for this call.
    for (uint8_t attempt = 0; attempt < 2; attempt++) {
        bool reused = _connected;
        _ensureConnected();
        int code = _http.POST(body);
        if (code > 0) {
            _drainBody();
            return;
        }
        _disconnect();
        if (!reused) {
            return;
        }
    }
}

void LogFireClass::_drainBody() {
    // Read the small response body ("OK"). Unread bytes make HTTPClient treat
    // the connection as alive even after the hub closed it.
    int remaining = _http.getSize();
    auto* stream = _http.getStreamPtr();
    if (!stream || remaining <= 0 || remaining > 64) {
        return;
    }
    uint8_t buffer[64];
    stream->readBytes(buffer, remaining);
}

void LogFireClass::log(const String& message, uint8_t level) {
    log(message.c_str(), level);
}
