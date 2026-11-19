# LogFire tests

Integration tests that run against a **disposable** Node-RED container. They
restart and hard-kill that container, so never point them at a hub you use.
Unit tests for the MicroPython clients live in `micropython/test_logfire.py`.
For their optional live checks, use
`python micropython/test_logfire.py --live --host 192.168.1.10 --port 1880`.
The selected port must serve both HTTP and UDP; the disposable hub below maps
them to separate ports, so use its dedicated hub and UI test commands instead.

The suite uses Python 3, Node.js, a C++17 host compiler, Docker or Podman, and
Playwright with its browser installed. Each test's dependencies are listed below.
Container tests use Node-RED 5.0.10; the hub itself does not require the host
compiler or browser test tools.

| Test | What it checks | Needs |
|---|---|---|
| `micropython/test_logfire.py` | Client unit tests (TCP + UDP, scripted sockets); `--live` sends to a hub | Python 3 |
| `tests/persistence_test.js` | Actual save/finalizer sources: deterministic shutdown interleavings, redeploy, failures, real filesystem flush | Node.js |
| `tests/arduino_retry_test.py` | Actual `LogFire.cpp` with scripted HTTP/WiFi stubs, compiled for both platform branches | Python 3, C++17 host compiler (`g++` by default) |
| `tests/persistence_lifecycle_test.py` | Real Node-RED stop/redeploy with a deliberately paused save, with and without new dirty data; creates/removes its own containers | Python 3, Docker or Podman |
| `tests/hub_test.py` | HTTP contract, parser (multi-line, CRLF, UDP), 3 MB cap on insert, persistence across restart, startup buffering, clean-stop flush, flood memory, SIGKILL during writes | Python 3, podman or docker |
| `tests/mp_tcp_idle_test.py` | `logfire.py` delivers every message after idle pauses (3-30 s) and at 5/8/12 s intervals | Python 3 |
| `tests/ui_test.py` | Browser UI: history, live WebSocket (HTTP + UDP), filter at all levels, clear button, console errors | Playwright (`tests/requirements.txt`) |

## 1. Start a disposable hub

First run the tests that do not require an existing hub:

```bash
node tests/persistence_test.js
python tests/arduino_retry_test.py
python tests/persistence_lifecycle_test.py --engine docker
```

Use `--cxx clang++` to select another C++ compiler, or `--cxx /path/to/zig
--compiler-arg c++` for Zig. The lifecycle test uses its own temporary containers
and an instrumented test flow; it never deploys the write-delay hook to your hub
or modifies `nodered/flow.json`. Use `--engine podman` to run it under Podman.

The following commands use Bash. Run them from the repository root. For Docker,
replace `podman` with `docker` and add `--engine docker` to the hub test command.

```bash
python nodered/build.py
podman run -d --name logfire-test -p 127.0.0.1:1881:1880/tcp -p 127.0.0.1:1882:1880/udp \
    docker.io/nodered/node-red:5.0.10
# Wait up to roughly one minute for the admin API, then fail if unavailable.
ready=0
for attempt in {1..30}; do
    if curl --fail --silent --max-time 1 http://127.0.0.1:1881/flows > /dev/null; then
        ready=1
        break
    fi
    sleep 1
done
if [ "$ready" -ne 1 ]; then
    podman logs logfire-test
    exit 1
fi
# The container is empty, so a full deploy is fine here (never on a shared hub):
curl --fail --show-error --silent --max-time 30 -X POST -H "Content-Type: application/json" -H "Node-RED-Deployment-Type: full" \
     --data @nodered/flow.json http://127.0.0.1:1881/flows
```

Use `127.0.0.1`, not `localhost`: with rootless podman `localhost` may resolve to
IPv6 `::1`, which is not forwarded.

## 2. Run

```bash
python micropython/test_logfire.py
python tests/hub_test.py --url http://127.0.0.1:1881 --udp 127.0.0.1:1882 --container logfire-test
python tests/mp_tcp_idle_test.py --host 127.0.0.1 --port 1881          # ~4 min, --quick ~1.5 min

python -m venv .venv && .venv/bin/pip install -r tests/requirements.txt
.venv/bin/playwright install chromium-headless-shell
.venv/bin/python tests/ui_test.py --url http://127.0.0.1:1881 --udp 127.0.0.1:1882
```

Use `--engine docker` for `hub_test.py` when the container runs under Docker.
For a shorter hub check that skips flood and kill rounds, replace the full hub
test command with:

```bash
python tests/hub_test.py --url http://127.0.0.1:1881 --udp 127.0.0.1:1882 --container logfire-test --quick
```

On Windows, the virtual environment executables are under `.venv\Scripts`:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r tests/requirements.txt
.venv\Scripts\python.exe -m playwright install chromium-headless-shell
.venv\Scripts\python.exe tests/ui_test.py --url http://127.0.0.1:1881 --udp 127.0.0.1:1882
```

## 3. Clean up

```bash
podman rm -f logfire-test
```

## Not covered

The Arduino host tests verify retry decisions with simulated HTTP responses.
They do not exercise the ESP networking libraries. Compile the examples with
`pio run -d arduino/LogFire/examples/platformio -e esp32 -e esp8266` and `pio ci`
for the TCP/UDP `.ino` examples as separate SDK checks. Network behavior still
needs hardware tests. CPython and MicroPython Unix tests do not verify Pico WiFi or
socket behavior. Physical-board TCP reconnect behavior and UDP delivery still
need testing on the supported boards. Process-kill tests do not simulate power
loss or prove a maximum data-loss interval.
