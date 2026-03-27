# 🔥 LogFire

> A tiny self-hosted debug logging system for WiFi-connected microcontrollers & IoT Devices.

Devices send plain text messages over HTTP, a Node-RED flow aggregates and auto-expires them, and a vanilla JS browser UI displays live logs in per-device tabs. Includes libraries for Arduino (ESP8266/ESP32) and MicroPython (Pico W).

---

## Goal

When developing on microcontrollers, `Serial.print` is your best friend — until your device is wireless, embedded, or across the room. LogFire replaces that habit with a single `log()` call that ships your message over WiFi to a local hub, where you can watch it live in the browser.

**The guiding principle: keep the controller-side code as lightweight as possible.**

- One setup call at boot
- One function to send a message
- No acknowledgement, no retry logic, no queue
- A failed send is silently discarded — it never blocks or crashes your main loop
- Zero external dependencies on the device beyond the standard WiFi and HTTP libraries

The complexity lives in the hub and the UI, not on your hardware.

---

## How it works

```text
[Your Device]  →  HTTP POST plain text  →  [Node-RED Hub]  →  WebSocket  →  [Browser UI]
```

Each log call sends a single plain text message in the format:

```text
DEVICENAME: your message here
DEVICENAME(-2): something to warn about
```

An optional log level (0–4) can be attached using the `(-N)` notation. Level 0 (plain) is the default when no level is specified.

| Level | Name | Color |
| --- | --- | --- |
| 0 | *(plain)* | white |
| 1 | INFO | green |
| 2 | WARN | yellow |
| 3 | ERROR | red |
| 4 | CRITICAL | purple |

Node-RED receives it, parses the device name and level, timestamps it, stores it in memory, and broadcasts it to any connected browser. Per-device logs are capped at 3 MB — oldest entries are evicted when the limit is reached. The browser UI shows a live tab per device with a filter dropdown to show only messages at or above a selected level.

---

## Repo structure

```text
logfire/
├── nodered/
│   ├── flow.json         # Node-RED flow (importable JSON)
│   ├── logfireUI.html    # Browser UI source (vanilla HTML/JS/CSS)
│   └── build.py          # Embeds logfireUI.html into flow.json
├── arduino/
│   └── LogFire/          # Library — drop into PlatformIO lib/ or Arduino libraries/
│       ├── LogFire.h
│       ├── LogFire.cpp
│       └── examples/
│           ├── arduinoIDE/arduinoIDE.ino
│           └── platformio/
│               ├── platformio.ini
│               └── src/main.cpp
└── micropython/          # MicroPython module (Pico W / Pico W2)
    ├── logfire.py
    └── example/main.py
```

---

## Quick start

> For a short step-by-step guide see [HOWTO.md](HOWTO.md).

### 1. Hub (Node-RED)

```bash
cd nodered && python build.py    # embeds the UI into the flow
```

Import `nodered/flow.json` into your Node-RED instance. The flow serves the UI at `GET /logfire` — no `httpStatic` setup needed. A test inject fires on deploy so you can verify the UI immediately at `http://<host>:<port>/logfire`.

Logs persist to `/data/logfire_logs.json` inside the Docker container and survive restarts. Per-device logs are capped at 3 MB — oldest entries are automatically evicted.

### 2. Arduino (PlatformIO)

Copy the `arduino/LogFire` folder into your PlatformIO project's `lib/` directory.

```cpp
#include <LogFire.h>

LogFire.begin("MyDevice", "192.168.1.100", 1880);

LogFire.log("Device booted");              // level 0 (plain)
LogFire.log("Sensor timeout", 2);          // level 2 (WARN)
LogFire.log("Flash write failed", 3);      // level 3 (ERROR)
```

### 3. MicroPython (Pico W / Pico W2)

Copy `micropython/logfire.py` to your Pico W.

```python
import logfire

logfire.init("MyPico", "192.168.1.100", 1880)

logfire.log("Device booted")               # level 0 (plain)
logfire.log("Sensor timeout", 2)           # level 2 (WARN)
logfire.log("Flash write failed", 3)       # level 3 (ERROR)
```

---

> For architecture and design rationale see [DESIGN.md](DESIGN.md).

---

## Requirements

- **Hub:** Node-RED (any machine on your local network)
- **Arduino:** ESP8266 or ESP32 with WiFi connected
- **MicroPython:** Raspberry Pi Pico W or Pico W2 with `urequests` available

---

## License

MIT
