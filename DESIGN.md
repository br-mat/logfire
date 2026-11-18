# LogFire — Design Decisions

| Decision | Reason |
| --- | --- |
| HTTP POST as the default transport | Works through most local network setups without extra config; UDP is available as an optional transport |
| Plain text body | No JSON parsing needed on the device side |
| Fire and forget | A dropped log message is acceptable — never worth risking a crash |
| Node-RED as hub | Visual, easy to modify, serves the UI, handles timers — no custom server code needed |
| Vanilla JS UI | No build step, no framework, just open and it works |
| UI embedded in flow | Single file to import — `build.py` merges HTML into the flow so no `httpStatic` setup needed |
| No library.properties | Minimal file count — PlatformIO picks up the lib folder as-is |
| File-backed log store | JSON file at `/data/logfire_logs.json` — survives Docker restarts, no database needed |
| 3 MB per-device cap | Size-based eviction keeps storage bounded — oldest entries are dropped first |
| Log levels 0–4 | Optional severity tag (`(-N)` wire format) — plain by default, color-coded in the UI |
| Persistent connection | Single reused TCP socket per device — avoids socket exhaustion from per-call HTTPClient/socket creation |
| No message buffering | Buffering conflicts with fire-and-forget and KISS — the persistent connection fix already eliminates socket exhaustion, which was the actual problem. Buffering would add complexity (ring buffer, flush timing, tick/flush API) for marginal benefit |
| `localOnly` / `local_only` mode | Opt-in flag that bypasses all HTTP/WiFi logic entirely — Serial output only. Solves two cases: offline test builds (no hub reachable) and time-sensitive firmware where the 1 s HTTP timeout on a dead hub is unacceptable. Keeps user code clean — one call at boot, no `#ifdef` guards around every `log()` |
| UDP transport *(experimental)* | Optional `LogFireUDP` / `logfire_udp.py` clients send one packet per message to the flow's UDP input on port 1880, using the same wire format, parser and storage as HTTP. They do not wait for a hub response, but DNS and socket operations can still take time. Packets may be lost, duplicated or reordered. HTTP stays the default; neither transport queues or retries failed messages. Requires `1880/udp` to be exposed by the hub. |

---

## Trust Model

LogFire assumes all devices on the LAN are trusted. The `/log`, `/logs`, `/devices`, and `/clear` endpoints have no authentication — any device on the same network can send logs or clear them. This is intentional for a private hobby project.

---

## Future Considerations

| Idea | Notes |
| --- | --- |
| Custom Docker hub (replace Node-RED) | A lightweight Python server (FastAPI or raw `http.server` + `websockets`) would be self-contained, natively support UDP, eliminate the `build.py` / flow import ritual, and be significantly lighter than a full Node.js runtime. Downside: reimplementing everything Node-RED currently provides for free (HTTP, WebSocket, timers, file persistence, UI serving, log eviction). Worth revisiting if the project grows or the Node-RED dependency becomes a real pain point |
