"""LogFire hub regression tests (HTTP, UDP, parser, size cap, persistence, crash safety).

Runs against a DISPOSABLE Node-RED container that has nodered/flow.json deployed.
Destructive tests restart and hard-kill that container.

Usage:
    python tests/hub_test.py --url http://127.0.0.1:1881 --udp 127.0.0.1:1882 \
        --container <throwaway-container> [--quick]

    --quick   skip the slow tests (flood memory, repeated hard kills)
Requires: podman (or docker via --engine docker) for the container tests.
Exit code: 0 all passed, 1 failures.
"""
import argparse
import http.client
import json
import os
import random
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--udp", required=True, help="host:port of the flow's UDP input")
ap.add_argument("--container", required=True)
ap.add_argument("--engine", default="podman")
ap.add_argument("--quick", action="store_true")
args = ap.parse_args()
if args.container in ("nodered", "node-red"):
    sys.exit("refusing to run destructive tests against the shared hub container")

URL = args.url.rstrip("/")
U = urllib.parse.urlparse(URL)
UDP = (args.udp.rsplit(":", 1)[0], int(args.udp.rsplit(":", 1)[1]))
FILE = "/data/logfire_logs.json"
CAP = 3 * 1024 * 1024
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  -> ' + str(detail) if detail else ''}", flush=True)


def engine(*cmd):
    return subprocess.run([args.engine, *cmd], capture_output=True, text=True)


def post(path, body, ctype="text/plain; charset=utf-8"):
    data = body if isinstance(body, bytes) else body.encode()
    req = urllib.request.Request(URL + path, data=data, method="POST", headers={"Content-Type": ctype})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.headers.get("content-type", ""), r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("content-type", ""), e.read().decode()


def logs():
    with urllib.request.urlopen(URL + "/logs", timeout=30) as r:
        return json.loads(r.read())


def clear(device):
    return post("/clear", json.dumps({"device": device}), "application/json")[0]


def udp(text):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.sendto(text.encode(), UDP)
    s.close()


def up(timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        try:
            urllib.request.urlopen(URL + "/devices", timeout=2).read()
            return True
        except Exception:  # noqa: BLE001
            time.sleep(0.3)
    return False


def ready(timeout=30):
    """Up and the log store restored (clear answers 503 while starting)."""
    end = time.time() + timeout
    while time.time() < end:
        if up(timeout) and clear("__probe__") == 200:
            return True
        time.sleep(0.3)
    return False


def file_state():
    """Read the saved file; works on running and stopped (killed) containers."""
    with tempfile.TemporaryDirectory() as tmp:
        target = os.path.join(tmp, "logs.json")
        if engine("cp", f"{args.container}:{FILE}", target).returncode != 0:
            return None, "missing"
        with open(target, encoding="utf-8", errors="replace") as f:
            text = f.read()
    if not text:
        return None, "EMPTY"
    try:
        return json.loads(text), "valid"
    except ValueError:
        return None, f"CORRUPT ({len(text)} bytes)"


def mem_mb():
    out = engine("stats", "--no-stream", "--format", "{{.MemUsage}}", args.container).stdout.strip()
    if not out:
        return None
    value = out.split("/")[0].strip().lower()      # podman: "280.1MB", docker: "1.2GiB"
    num = float("".join(c for c in value if c.isdigit() or c == "."))
    if value.endswith(("gb", "gib")):
        return num * 1000
    if value.endswith(("kb", "kib")):
        return num / 1000
    return num


def compact_size(entries):
    return len(json.dumps(entries, separators=(",", ":"), ensure_ascii=False).encode())


def flood(device, count, size, connection=None):
    c = connection or http.client.HTTPConnection(U.hostname, U.port, timeout=60)
    chunk = "x" * size
    for i in range(count):
        c.request("POST", "/log", body=f"{device}: {i:06d} {chunk}", headers={"Content-Type": "text/plain"})
        c.getresponse().read()
    c.close()


if not ready():
    sys.exit(f"hub at {URL} not ready")

# ── 1. HTTP contract ──────────────────────────────────────────────────────────
print("1. HTTP contract")
st, ct, body = post("/log", "hubTest(-4): Grüße 🔥 critical")
check("POST /log -> 200 OK, text/plain", st == 200 and body == "OK" and ct.startswith("text/plain"), (st, ct, body))
for label, payload, expect in [
    ("no separator", "garbage", "Bad format"),
    ("empty body", "", "Bad format"),
    ("reserved name", "__proto__: x", "Invalid device name"),
    ("control char in name", "bad\tname: x", "Invalid device name"),
    ("name > 64 chars", "d" * 65 + ": x", "Invalid device name"),
]:
    st, _, body = post("/log", payload)
    check(f"{label} -> 400", st == 400 and expect in body, (st, body))
check("POST /clear without device -> 400", post("/clear", "{}", "application/json")[0] == 400)
check("POST /clear -> 200", clear("hubTest") == 200 and "hubTest" not in logs())

# ── 2. Parser ─────────────────────────────────────────────────────────────────
print("2. Parser (multi-line, trailing newline, CRLF; TCP and UDP)")
cases = [
    ("tcp", "pT(-3): Guru Meditation\n  at loop()\n  at setup()", 3, "Guru Meditation\n  at loop()\n  at setup()"),
    ("tcp", "pT(-2): sensor offline\n", 2, "sensor offline"),
    ("tcp", "pT(-1): windows line\r\n", 1, "windows line"),
    ("tcp", "pT: line1\nline2", 0, "line1\nline2"),
    ("udp", "pU(-4): udp trailing newline\n", 4, "udp trailing newline"),
    ("udp", "pU(-3): udp\nmulti", 3, "udp\nmulti"),
]
for transport, text, _, _ in cases:
    post("/log", text) if transport == "tcp" else udp(text)
time.sleep(1)
data = logs()
check("no bogus devices like 'pT(-3)'", not any("(-" in d for d in data), sorted(data))
for transport, text, level, message in cases:
    device = text.split("(")[0].split(":")[0]
    found = any(e["level"] == level and e["message"] == message for e in data.get(device, []))
    check(f"{transport}: {text[:28]!r} -> {device} level {level}", found)
clear("pT"); clear("pU")

# ── 3. Size cap on insert ─────────────────────────────────────────────────────
print("3. Size cap enforced on insert (no 60 s wait)")
flood("capTest", 1800, 2000)
entries = logs().get("capTest", [])
size = compact_size(entries)
check(f"per-device size <= {CAP} bytes right after the burst", size <= CAP, f"{size} bytes, {len(entries)} entries")
check("oldest evicted, newest kept",
      entries and entries[-1]["message"].startswith("001799") and not entries[0]["message"].startswith("000000"),
      f"first={entries[0]['message'][:6] if entries else None}")
clear("capTest")

# ── 4. Persistence ────────────────────────────────────────────────────────────
print("4. Persistence across restart, logs during startup")
post("/log", "persistTest(-2): before restart")
time.sleep(3)  # save interval is 2 s
accepted, stop = [], threading.Event()


def spam():
    i = 0
    while not stop.is_set():
        try:
            st, _, _ = post("/log", f"startupTest: during start #{i}")
            if st == 200:
                accepted.append(f"during start #{i}")
        except Exception:  # noqa: BLE001
            pass
        i += 1
        time.sleep(0.02)


engine("restart", "-t", "5", args.container)
t = threading.Thread(target=spam)
t.start()
check("hub back up after restart", ready())
time.sleep(4)
stop.set(); t.join(); time.sleep(1)
data = logs()
check("log from before restart survived",
      any(e["message"] == "before restart" for e in data.get("persistTest", [])))
stored = {e["message"] for e in data.get("startupTest", [])}
lost = [m for m in accepted if m not in stored]
check(f"no accepted log lost during startup ({len(accepted)} accepted)", not lost, f"{len(lost)} lost")
post("/log", "stopTest: written right before a clean stop")
engine("stop", "-t", "10", args.container); engine("start", args.container); ready()
check("clean stop flushes unsaved logs (finalize)", "stopTest" in logs())
for d in ("persistTest", "startupTest", "stopTest"):
    clear(d)

if not args.quick:
    # ── 5. Flood: memory stays bounded ────────────────────────────────────────
    print("5. Flood from one sender (12000 x 2 KB, sequential)")
    before = mem_mb()
    peak = before or 0
    c = http.client.HTTPConnection(U.hostname, U.port, timeout=60)
    chunk = "x" * 2000
    alive = True
    for i in range(12000):
        try:
            c.request("POST", "/log", body=f"floodTest: {i:06d} {chunk}", headers={"Content-Type": "text/plain"})
            c.getresponse().read()
        except Exception as e:  # noqa: BLE001
            alive = False
            print(f"    failed after {i} messages: {e}")
            break
        if i % 2000 == 1999:
            m = mem_mb() or 0
            peak = max(peak, m)
            print(f"    {i + 1:6} sent, hub memory {m:.0f} MB", flush=True)
    c.close()
    check("hub survived the flood", alive and up(5))
    check("hub memory stayed below 500 MB", peak < 500, f"start {before:.0f} MB, peak {peak:.0f} MB")
    time.sleep(3)
    data, state = file_state()
    check("saved file valid and capped", state == "valid" and compact_size(data.get("floodTest", [])) <= CAP, state)
    clear("floodTest")

    # ── 6. Hard kills during writes ───────────────────────────────────────────
    print("6. Hard kill (SIGKILL) during writes, 8 rounds")
    flood("killBase", 1500, 2000)  # ~3 MB of history that must survive
    time.sleep(3)
    bad = []
    for k in range(8):
        stop = threading.Event()

        def writer():
            try:
                c = http.client.HTTPConnection(U.hostname, U.port, timeout=10)
                i = 0
                while not stop.is_set():
                    c.request("POST", "/log", body=f"killTest: {k}-{i} " + "y" * 500,
                              headers={"Content-Type": "text/plain"})
                    c.getresponse().read()
                    i += 1
            except Exception:  # noqa: BLE001
                pass

        t = threading.Thread(target=writer)
        t.start()
        time.sleep(random.uniform(1.5, 4.0))
        engine("kill", "-s", "KILL", args.container)
        stop.set(); t.join()
        data, state = file_state()
        engine("start", args.container); ready()
        history = len(logs().get("killBase", []))
        print(f"    kill {k + 1}: file {state}, killBase entries after restart: {history}", flush=True)
        if state != "valid" or history < 1000:
            bad.append(k + 1)
    check("file always valid and history kept after every kill", not bad, f"bad rounds: {bad}")
    clear("killBase"); clear("killTest")

print(f"\nResults: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
