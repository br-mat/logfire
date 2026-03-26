# 🔥 LogFire

> A tiny self-hosted debug logging system for WiFi-connected microcontrollers.

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

```
[Your Device]  →  HTTP POST plain text  →  [Node-RED Hub]  →  WebSocket  →  [Browser UI]
```

Each log call sends a single plain text message in the format:

```
DEVICENAME: your message here
```

Node-RED receives it, parses the device name, timestamps it, stores it in memory, and broadcasts it to any connected browser. Log entries auto-expire after 30 minutes. The browser UI shows a live tab per device.

---

## Repo structure

```
logfire/
├── nodered/
│   ├── flow.json     # Node-RED flow (importable JSON)
│   ├── index.html    # Browser UI source (vanilla HTML/JS/CSS)
│   └── build.py      # Embeds index.html into flow.json
├── arduino/
│   ├── LogFire/      # Library (ESP8266 / ESP32, drop into PlatformIO lib/)
│   │   ├── LogFire.h
│   │   └── LogFire.cpp
│   └── example/      # PlatformIO example project
│       ├── platformio.ini
│       └── src/main.cpp
└── micropython/      # MicroPython module (Pico W)
    └── logfire.py
```

---

## Quick start

### 1. Hub (Node-RED)

```bash
cd nodered && python build.py    # embeds the UI into the flow
```

Import `nodered/flow.json` into your Node-RED instance. The flow serves the UI at `GET /logfire` — no `httpStatic` setup needed. A test inject fires on deploy so you can verify the UI immediately at `http://<host>:<port>/logfire`.

Logs persist to `/data/logfire_logs.json` inside the Docker container and survive restarts. Entries auto-expire after 24 hours.

### 2. Arduino (PlatformIO)

Copy the `arduino/LogFire` folder into your PlatformIO project's `lib/` directory.

```cpp
#include <LogFire.h>

LogFire.begin("MyDevice", "192.168.1.100", 1880);

LogFire.log("Warning: data could not be fetched!");
```

### 3. MicroPython (Pico W)
Copy `micropython/logfire.py` to your Pico W.

```python
import logfire

logfire.init("MyPico", "192.168.1.100", 1880)

logfire.log("Warning: data could not be fetched!")
```

---

## Design decisions

| Decision | Reason |
|---|---|
| HTTP POST over UDP | Slightly more reliable, works through most local network setups without extra config |
| Plain text body | No JSON parsing needed on the device side |
| Fire and forget | A dropped log message is acceptable — never worth risking a crash |
| Node-RED as hub | Visual, easy to modify, serves the UI, handles timers — no custom server code needed |
| Vanilla JS UI | No build step, no framework, just open and it works |
| UI embedded in flow | Single file to import — `build.py` merges HTML into the flow so no `httpStatic` setup needed |
| No library.properties | Minimal file count — PlatformIO picks up the lib folder as-is |
| File-backed log store | JSON file at `/data/logfire_logs.json` — survives Docker restarts, no database needed |
| 24h auto-expire | Keeps logs useful without unbounded growth |

---

## Requirements

- **Hub:** Node-RED (any machine on your local network)
- **Arduino:** ESP8266 or ESP32 with WiFi connected
- **MicroPython:** Raspberry Pi Pico W with `urequests` available

---

## License

MIT
