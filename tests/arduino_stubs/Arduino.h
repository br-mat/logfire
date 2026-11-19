#pragma once
#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>

class String {
public:
    String() = default;
    String(const char* value) : text(value) {}
    String(unsigned int value) : text(std::to_string(value)) {}
    explicit String(std::string value) : text(std::move(value)) {}
    const char* c_str() const { return text.c_str(); }
    friend String operator+(const String& left, const String& right) {
        return String(left.text + right.text);
    }
private:
    std::string text;
};

struct SerialStub {
    template <class T> void print(const T&) {}
    template <class T> void println(const T&) {}
};
inline SerialStub Serial;
