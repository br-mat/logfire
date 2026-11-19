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
| File-backed log store | JSON snapshots at `/data/logfire_logs.json`, with no database. A timer attempts to save pending changes every two seconds instead of serializing on every message. Each save uses its own temporary file, fsync and rename. On stop/redeploy, the node blocks older saves from publishing and synchronously flushes pending data, including in-flight snapshots. The final rename and shutdown flush are synchronous; bulk periodic writes remain asynchronous. Unexpected stops can lose changes since the last successful save; HTTP success does not acknowledge a disk write. Keep `/data` on a persistent volume |
| 3 MB per-device cap | Enforced on every insert from a per-device byte count; oldest entries are dropped first. A 60 s job recomputes exact sizes as a safety net. Device count is not capped, so total hub memory is not bounded by this limit |
| Log levels 0–4 | Optional severity tag (`(-N)` wire format) — plain by default, color-coded in the UI |
| Persistent connection | One reused TCP socket per device avoids creating a connection for every message. Clients read responses completely. The retry policy allows one reconnect and resend after failure on a reused connection, which can duplicate a message if only the response was lost. MicroPython also reconnects before sending after more than 4 s idle. Hub idle timeouts depend on deployment |
| No device-side message queue | Failed messages are discarded after the permitted reconnect attempt. Devices do not retain logs for later delivery. The hub separately buffers received logs in memory between saves |
| `localOnly` / `local_only` mode | Makes log calls use Serial/REPL output without network operations. Useful for offline development and time-sensitive firmware. Socket timeouts are not total limits on call duration; DNS, connection, response and retry work can add time |
| UDP transport *(experimental)* | Optional `LogFireUDP` / `logfire_udp.py` clients send one packet per message to UDP port 1880, using the same format, parser and storage as HTTP. They do not wait for a response or retry. DNS and socket operations can still take time. Packets may be lost, duplicated or reordered. HTTP remains the default and permits one reconnect retry; neither transport has a device-side message queue. Expose `1880/udp` when using UDP |

---

## Trust Model

LogFire assumes all devices on the LAN are trusted. The `/log`, `/logs`, `/devices`, and `/clear` endpoints have no authentication — any device on the same network can send logs or clear them. This is intentional for a private hobby project.

---

## Future Considerations

| Idea | Notes |
| --- | --- |
| Custom Docker hub (replace Node-RED) | A lightweight Python server (FastAPI or raw `http.server` + `websockets`) would be self-contained, natively support UDP, eliminate the `build.py` / flow import ritual, and be significantly lighter than a full Node.js runtime. Downside: reimplementing everything Node-RED currently provides for free (HTTP, WebSocket, timers, file persistence, UI serving, log eviction). Worth revisiting if the project grows or the Node-RED dependency becomes a real pain point |
