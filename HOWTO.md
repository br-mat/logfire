# LogFire — How To Use

## 1. Hub (Node-RED)

1. Run `cd nodered && python build.py` to embed the UI into the flow
2. Open Node-RED and import `nodered/flow.json`
3. Deploy the flow
4. Open `http://<host>:<port>/logfire` in your browser — a test log appears automatically

> Logs persist to `/data/logfire_logs.json` and survive restarts. Entries older than 24h are removed automatically.

---

## 2. Arduino (ESP32 / ESP8266)

1. Copy `arduino/LogFire/` into your project's `lib/` directory (PlatformIO) or `~/Arduino/libraries/` (Arduino IDE)
2. Include the library and add two calls:

```cpp
#include <LogFire.h>

// In setup() — after WiFi is connected
LogFire.begin("DeviceName", "10.0.0.20", 1880);

// Anywhere in your code
LogFire.log("your message here");
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
logfire.init("DeviceName", "10.0.0.20", 1880)

# Anywhere in your code
logfire.log("your message here")
```

> `urequests` must be available on your device. A failed send is silently discarded.

See [`micropython/example/main.py`](micropython/example/main.py) for a full working example.
