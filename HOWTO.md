# LogFire — How To Use

## 1. Hub (Node-RED)

1. Run `cd nodered && python build.py` to embed the UI into the flow
2. Open Node-RED and import `nodered/flow.json`
3. Deploy the flow
4. Open `http://<host>:<port>/logfire` in your browser — a test log appears automatically

> Logs persist to `/data/logfire_logs.json` and survive restarts. Per-device logs are capped at 3 MB — oldest entries are evicted automatically.

---

## 2. Arduino (ESP32 / ESP8266)

1. Copy `arduino/LogFire/` into your project's `lib/` directory (PlatformIO) or `~/Arduino/libraries/` (Arduino IDE)
2. Include the library and add two calls:

```cpp
#include <LogFire.h>

// In setup() — after WiFi is connected
LogFire.begin("DeviceName", "10.0.0.XX", 1880);

// Anywhere in your code
LogFire.log("your message here");           // level 0 (plain)
LogFire.log("something is off", 2);         // level 2 (WARN — yellow)
```

Log levels: 0 = plain (default), 1 = INFO (green), 2 = WARN (yellow), 3 = ERROR (red), 4 = CRITICAL (purple).

Each `log()` call also prints to Serial by default — same format as the web UI. To disable:

```cpp
LogFire.mirrorSerial(false);
```

> WiFi must already be connected. A failed send is silently discarded — your loop never blocks.

See [`arduino/LogFire/examples/`](arduino/LogFire/examples/) for full working examples.

---

## 3. MicroPython (Pico W / Pico W2)

1. Copy `micropython/logfire.py` to your Pico W (alongside your `main.py`)
2. Add two calls:

```python
import logfire

# At boot — after WiFi is connected
logfire.init("DeviceName", "10.0.0.XX", 1880)

# Anywhere in your code
logfire.log("your message here")            # level 0 (plain)
logfire.log("something is off", 2)          # level 2 (WARN — yellow)
```

Log levels: 0 = plain (default), 1 = INFO (green), 2 = WARN (yellow), 3 = ERROR (red), 4 = CRITICAL (purple).

Each `log()` call also prints to the REPL by default. To disable:

```python
logfire.mirror_serial(False)
```

> A failed send is silently discarded.

See [`micropython/example/main.py`](micropython/example/main.py) for a full working example.
