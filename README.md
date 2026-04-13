# LogFire

A small debug logging setup I put together for WiFi microcontroller projects. When the device is wireless or across the room, `log()` sends the message over HTTP to a Node-RED hub — you can watch it live in the browser. Serial output is mirrored by default so the existing workflow stays intact. Libraries for Arduino (ESP8266/ESP32) and MicroPython (Pico W).

---

## How it works

```text
[Your Device]  →  HTTP POST plain text  →  [Node-RED Hub]  →  WebSocket  →  [Browser UI]
```

The library formats each message automatically before sending:

```text
DEVICENAME: your message here
DEVICENAME(-2): something to warn about
```

The device name and log level are added by the library — you only pass the message string and an optional level integer to `log()`.

| Level | Name | Color |
| --- | --- | --- |
| 0 | *(plain)* | white |
| 1 | INFO | green |
| 2 | WARN | yellow |
| 3 | ERROR | red |
| 4 | CRITICAL | purple |

Node-RED receives it, parses the device name and level, timestamps it, and stores it in memory. Logs can be observed live at `http://<node-red-host>:1880/logfire`. Per-device logs are capped at 3 MB — oldest entries are evicted when the limit is reached. The browser UI shows a live tab per device with a filter dropdown.

---

## Quick start

> For a step-by-step guide see [HOWTO.md](HOWTO.md).

### 1. Hub (Node-RED)

Run `python nodered/build.py` to embed the UI into the flow, then import `nodered/flow.json` into Node-RED. The flow serves the UI at `GET /logfire`.

Logs persist to `/data/logfire_logs.json` inside the Docker container and survive restarts.

### 2. Arduino (ESP32 / ESP8266)

Copy `arduino/LogFire/` into your project's `lib/` directory.

```cpp
#include <LogFire.h>

LogFire.begin("MyDevice", "192.168.1.100", 1880);

LogFire.log("Device booted");              // level 0 (plain)
LogFire.log("Sensor timeout", 2);          // level 2 (WARN)
// LogFire.mirrorSerial(false);            // disable Serial echo (on by default)
// LogFire.localOnly(true);               // Serial only, no network
```

See [`arduino/LogFire/examples/`](arduino/LogFire/examples/) for full examples.

### 3. MicroPython (Pico W / Pico W2)

Copy `micropython/logfire.py` to your Pico W:

```python
import logfire

logfire.init("MyPico", "192.168.1.100", 1880)

logfire.log("Device booted")               # level 0 (plain)
logfire.log("Sensor timeout", 2)           # level 2 (WARN)
# logfire.mirror_serial(False)             # disable print echo (on by default)
# logfire.local_only(True)                 # Serial only, no network
```

See [`micropython/example/main.py`](micropython/example/main.py) for a full example.

---

## Requirements

- **Hub:** Node-RED (any machine on your local network)
- **Arduino:** ESP8266 or ESP32 with WiFi connected
- **MicroPython:** Raspberry Pi Pico W or Pico W2

---

## License

MIT
