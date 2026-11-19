// Compile this harness with the real LogFire.cpp and the minimal host stubs.
#include "LogFire.h"
#include <functional>
#include <iostream>
#include <stdexcept>

void require(bool condition, const char* message) {
    if (!condition) throw std::runtime_error(message);
}

int main() {
    int passed = 0, failed = 0;
    auto test = [&](const char* name, const std::function<void(LogFireClass&)>& body) {
        scripted::reset(); WiFi.connection = WL_CONNECTED;
        LogFireClass client;
        client.begin("host-test", "127.0.0.1"); client.mirrorSerial(false);
        try {
            body(client);
            require(scripted::responses.empty(), "missing POST");
            std::cout << "PASS " << name << '\n'; passed++;
        } catch (const std::exception& error) {
            std::cerr << "FAIL " << name << ": " << error.what() << '\n'; failed++;
        }
    };
    test("fresh failure sends once and next call starts fresh", [](LogFireClass& client) {
        scripted::responses = {-1}; client.log("first");
        require(scripted::posts == 1 && scripted::ends == 1, "fresh failure was retried");
        scripted::responses = {-1}; client.log("second");
        require(scripted::posts == 2 && scripted::begins == 2, "failed connection retained");
    });
    test("reused failure reconnects once and succeeds", [](LogFireClass& client) {
        scripted::responses = {200}; client.log("prime"); scripted::reset();
        scripted::responses = {-1, 200}; client.log("retry");
        require(scripted::posts == 2 && scripted::begins == 1 && scripted::ends == 1,
                "wrong reconnect sequence");
        require(scripted::drained == 2, "retry response not drained");
    });
    test("two failures on reused connection stop after one retry", [](LogFireClass& client) {
        scripted::responses = {200}; client.log("prime"); scripted::reset();
        scripted::responses = {-1, -1}; client.log("retry");
        require(scripted::posts == 2 && scripted::begins == 1 && scripted::ends == 2,
                "wrong retry limit or disconnect");
    });
    test("success sends once, formats message and drains response", [](LogFireClass& client) {
        scripted::responses = {200}; client.log("hello", 2);
        require(scripted::posts == 1 && scripted::begins == 1, "wrong success request count");
        require(scripted::drained == 2, "response not drained");
        require(scripted::body == "host-test(-2): hello", "wrong message format");
    });
    test("successful reused connection needs no new begin", [](LogFireClass& client) {
        scripted::responses = {200}; client.log("prime"); scripted::reset();
        scripted::responses = {200}; client.log(String("reused"));
        require(scripted::posts == 1 && scripted::begins == 0, "successful connection not reused");
        require(scripted::drained == 2, "response not drained");
    });
    test("HTTP error response is not a transport retry", [](LogFireClass& client) {
        scripted::responses = {503}; client.log("busy");
        require(scripted::posts == 1 && scripted::drained == 2, "HTTP error retried or undrained");
    });
    test("local-only and offline calls do not send", [](LogFireClass& client) {
        client.localOnly(true); client.log("local");
        client.localOnly(false); WiFi.connection = 0; client.log("offline");
        require(scripted::posts == 0 && scripted::begins == 0, "unexpected network request");
    });
    std::cout << passed << '/' << (passed + failed) << " Arduino retry checks passed\n";
    return failed ? 1 : 0;
}
