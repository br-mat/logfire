#pragma once
#include "Arduino.h"
#include "WiFiClient.h"
#include <deque>
#include <stdexcept>

namespace scripted {
inline std::deque<int> responses;
inline int posts = 0, begins = 0, ends = 0, drained = 0;
inline std::string body;
inline void reset() {
    responses.clear();
    posts = begins = ends = drained = 0;
    body.clear();
}
}

struct StreamStub {
    std::size_t readBytes(uint8_t*, std::size_t size) {
        scripted::drained += static_cast<int>(size);
        return size;
    }
};

class HTTPClient {
public:
    void begin(const String&) { scripted::begins++; }
    void begin(WiFiClient&, const String&) { scripted::begins++; }
    void end() { scripted::ends++; }
    void setTimeout(int) {}
    void setConnectTimeout(int) {}
    void addHeader(const char*, const char*) {}
    void setReuse(bool) {}
    int POST(const String& body) {
        scripted::posts++;
        scripted::body = body.c_str();
        if (scripted::responses.empty()) throw std::runtime_error("unexpected extra POST");
        int result = scripted::responses.front();
        scripted::responses.pop_front();
        return result;
    }
    int getSize() const { return 2; }
    StreamStub* getStreamPtr() { return &stream; }
private:
    StreamStub stream;
};
