#pragma once
constexpr int WL_CONNECTED = 3;
struct WiFiStub {
    int connection = WL_CONNECTED;
    int status() const { return connection; }
};
inline WiFiStub WiFi;
