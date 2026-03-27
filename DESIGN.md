# LogFire — Design Decisions

| Decision | Reason |
| --- | --- |
| HTTP POST over UDP | Slightly more reliable, works through most local network setups without extra config |
| Plain text body | No JSON parsing needed on the device side |
| Fire and forget | A dropped log message is acceptable — never worth risking a crash |
| Node-RED as hub | Visual, easy to modify, serves the UI, handles timers — no custom server code needed |
| Vanilla JS UI | No build step, no framework, just open and it works |
| UI embedded in flow | Single file to import — `build.py` merges HTML into the flow so no `httpStatic` setup needed |
| No library.properties | Minimal file count — PlatformIO picks up the lib folder as-is |
| File-backed log store | JSON file at `/data/logfire_logs.json` — survives Docker restarts, no database needed |
| 3 MB per-device cap | Size-based eviction keeps storage bounded — oldest entries are dropped first |
| Log levels 0–4 | Optional severity tag (`(-N)` wire format) — plain by default, color-coded in the UI |
