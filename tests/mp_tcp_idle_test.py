"""Delivery test for micropython/logfire.py (TCP) across idle periods, on CPython.

The hub closes idle keep-alive connections after 5 s. This sends messages
after pauses of 3-30 s and at fixed intervals, then checks /logs that every
message arrived.

Usage: python tests/mp_tcp_idle_test.py --host 127.0.0.1 --port 1881 [--quick]
Exit code: 0 all delivered, 1 otherwise.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "micropython"))
import logfire  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--host", required=True)
ap.add_argument("--port", type=int, default=1880)
ap.add_argument("--quick", action="store_true", help="shorter pauses only")
args = ap.parse_args()
BASE = f"http://{args.host}:{args.port}"
results = []


def stored(device):
    data = json.loads(urllib.request.urlopen(BASE + "/logs", timeout=10).read())
    return [e["message"] for e in data.get(device, [])]


def clear(device):
    req = urllib.request.Request(BASE + "/clear", data=json.dumps({"device": device}).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  -> ' + detail if detail else ''}", flush=True)


logfire.mirror_serial(False)

print("Idle pauses (message before, pause, 5 messages after)")
for pause in ((3, 6, 10) if args.quick else (3, 6, 10, 30)):
    device = f"mpIdle{pause}"
    clear(device)
    logfire.init(device, args.host, args.port)
    logfire.log("before")
    time.sleep(pause)
    for n in "ABCDE":
        logfire.log("after " + n)
    time.sleep(1)
    got = stored(device)
    expected = ["before"] + ["after " + n for n in "ABCDE"]
    lost = [m for m in expected if m not in got]
    check(f"pause {pause:2} s: all 6 delivered", not lost, f"lost {lost}" if lost else "")
    clear(device)

print("Periodic logging")
for interval, count in (((5, 6), (8, 5)) if args.quick else ((5, 8), (8, 9), (12, 6))):
    device = f"mpEvery{interval}"
    clear(device)
    logfire.init(device, args.host, args.port)
    for i in range(count):
        logfire.log(f"tick {i}")
        time.sleep(interval)
    got = stored(device)
    check(f"every {interval:2} s: {count}/{count} delivered", len(got) == count, f"{len(got)}/{count}")
    clear(device)

logfire._disconnect()
print(f"\nResults: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
