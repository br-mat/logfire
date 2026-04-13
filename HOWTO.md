# LogFire — How To Use

## 1. Hub (Node-RED)

The Node-RED flow handles the server side — receiving messages, parsing them, storing them per device, and serving the browser UI.

`nodered/build.py` embeds `logfireUI.html` into `flow.json` so the UI is self-contained inside the flow. Run it once before importing, or again any time you edit the UI file:

```bash
python nodered/build.py
```

Then import `nodered/flow.json` into Node-RED via the hamburger menu → **Import**. After deploying, open `http://<host>:<port>/logfire` in your browser. A test log fires automatically on deploy so you can confirm it's working before connecting any device.

Logs are stored in `/data/logfire_logs.json` inside the Docker container and loaded back on restart. Each device's log is capped at 3 MB — when it fills up, the oldest entries are dropped.

### Docker port mapping

If running Node-RED in Docker, expose both TCP and UDP on port 1880. TCP is needed for the HTTP interface; UDP is needed for the `LogFireUDP` / `logfire_udp` variants.

```yaml
ports:
  - "1880:1880/tcp"
  - "1880:1880/udp"
```

Or with `docker run`:

```bash
docker run -p 1880:1880/tcp -p 1880:1880/udp nodered/node-red
```

If your host has a firewall (e.g. `ufw`):

```bash
sudo ufw allow 1880/tcp
sudo ufw allow 1880/udp
```

---

## 2. Arduino (ESP32 / ESP8266)

`arduino/LogFire/` is a standard Arduino library. Copy it into your PlatformIO project's `lib/` directory, or into `~/Arduino/libraries/` for the Arduino IDE.

Include the header and call `begin()` once in `setup()`, after WiFi is already connected. Pass it a device name (labels the tab in the UI), the IP of your Node-RED host, and the port (default 1880).

```cpp
#include <LogFire.h>

LogFire.begin("DeviceName", "10.0.0.XX", 1880);
```

Then call `log()` anywhere:

```cpp
LogFire.log("your message here");           // level 0 (plain)
LogFire.log("something is off", 2);         // level 2 (WARN — yellow)
LogFire.log("something broke", 3);          // level 3 (ERROR — red)
```

Log levels: 0 = plain (default), 1 = INFO (green), 2 = WARN (yellow), 3 = ERROR (red), 4 = CRITICAL (purple).

Each `log()` call also prints to Serial by default, so you don't lose your existing Serial workflow. To disable:

```cpp
LogFire.mirrorSerial(false);
```

For Serial-only logging without network traffic (useful during development without a hub):

```cpp
LogFire.localOnly(true);
```

If a send fails, the connection is closed and retried on the next call — `log()` never blocks your main loop.

See [`arduino/LogFire/examples/`](arduino/LogFire/examples/) for full working examples.

---

## 3. MicroPython (Pico W / Pico W2)

`logfire.py` is a single-file module — copy it alongside your `main.py`. It handles WiFi sends and REPL mirroring with no dependencies beyond the standard MicroPython libraries.

Call `init()` once at boot after WiFi is connected:

```python
import logfire

logfire.init("DeviceName", "10.0.0.XX", 1880)
```

Then call `log()` anywhere:

```python
logfire.log("your message here")            # level 0 (plain)
logfire.log("something is off", 2)          # level 2 (WARN — yellow)
logfire.log("something broke", 3)           # level 3 (ERROR — red)
```

Log levels: 0 = plain (default), 1 = INFO (green), 2 = WARN (yellow), 3 = ERROR (red), 4 = CRITICAL (purple).

Each `log()` call also prints to the REPL by default. To disable:

```python
logfire.mirror_serial(False)
```

For Serial-only logging without network traffic:

```python
logfire.local_only(True)
```

If a send fails, the connection is closed and retried on the next call.

See [`micropython/example/main.py`](micropython/example/main.py) for a full working example.
