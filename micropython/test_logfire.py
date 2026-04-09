"""
LogFire test script — development use only.

Verifies the logfire.py module logic on standard CPython (no Pico needed).
Not intended for deployment — the example/ folder contains the usage reference.

Tests:
  1. local_only skips network (proved by timing against unreachable host)
  2. local_only prints to stdout correctly
  3. mirror_serial=False suppresses output in local_only mode
  4. local_only=False restores normal network path
  5. Live send to actual hub (optional)

Usage:
  python test_logfire.py           # runs all tests, skips live hub test
  python test_logfire.py --live    # also sends a real message to LOGFIRE_HOST:LOGFIRE_PORT
"""

LOGFIRE_HOST = "10.0.0.XX"   # set to your hub's IP before running --live
LOGFIRE_PORT = 1880

import sys
import time
import importlib

# Reset module state between tests
def fresh():
    if "logfire" in sys.modules:
        del sys.modules["logfire"]
    import logfire
    return logfire

PASS = "PASS"
FAIL = "FAIL"

results = []

def check(name, ok):
    tag = PASS if ok else FAIL
    print(f"  [{tag}] {name}")
    results.append((name, ok))


# ── Test 1: local_only skips network (timing proof) ──────────────────────────
print("\nTest 1: local_only skips network entirely")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)  # routable but unreachable address
lf.local_only(True)
lf.mirror_serial(False)

t0 = time.time()
for _ in range(10):
    lf.log("should be instant", 1)
elapsed = time.time() - t0

# 10 calls should complete in well under 100ms if no network is touched.
# If local_only were broken and it tried to connect, it would stall for seconds.
check("10 log() calls complete in <0.1s with unreachable host", elapsed < 0.1)


# ── Test 2: local_only prints to stdout ──────────────────────────────────────
print("\nTest 2: local_only mirrors to stdout")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.local_only(True)

print("  (expect 5 lines of output below)")
lf.log("plain message")
lf.log("info message", 1)
lf.log("warn message", 2)
lf.log("error message", 3)
lf.log("critical message", 4)
check("no exception during output", True)


# ── Test 3: mirror_serial=False + local_only --silent ────────────────────────
print("\nTest 3: mirror_serial=False + local_only --no output, no network")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)
lf.local_only(True)

t0 = time.time()
lf.log("this should produce no output and return instantly")
elapsed = time.time() - t0
check("returns instantly (<0.05s)", elapsed < 0.05)
print("  (no output above = correct)")


# ── Test 4: local_only(False) restores network path ──────────────────────────
print("\nTest 4: local_only(False) re-enables network path")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.local_only(True)
lf.mirror_serial(False)
lf.log("local only")           # should be instant

lf.local_only(False)           # re-enable network
lf.mirror_serial(False)
t0 = time.time()
lf.log("now tries network")    # should attempt TCP connect --stall/fail on unreachable host
elapsed = time.time() - t0

# We expect it to take >0.5s (hitting the socket timeout on an unreachable host)
# which confirms the network path was actually re-enabled.
check("network path re-enabled after local_only(False) (took >0.5s)", elapsed > 0.5)


# ── Test 5: local_only(True) disconnects an existing connection ───────────────
print("\nTest 5: local_only(True) disconnects existing socket")
lf = fresh()
lf.local_only(True)            # set before init — should be a no-op on _disconnect
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)

# Force _connected = True manually to simulate an existing connection
import logfire as _lf_mod
_lf_mod._connected = True
_lf_mod._sock = None           # no real socket, but flag is True

lf.local_only(True)            # should call _disconnect(), resetting _connected
check("_connected reset to False after local_only(True)", not _lf_mod._connected)


# ── Test 6: Live hub send (optional) ─────────────────────────────────────────
if "--live" in sys.argv:
    print("\nTest 6: Live send to {}:{}".format(LOGFIRE_HOST, LOGFIRE_PORT))
    lf = fresh()
    lf.init("pylog", LOGFIRE_HOST, LOGFIRE_PORT)
    try:
        lf.log("LogFire Python test — plain")
        lf.log("LogFire Python test — INFO", 1)
        lf.log("LogFire Python test — WARN", 2)
        lf.log("LogFire Python test — ERROR", 3)
        check("live send completed without exception", True)
    except Exception as e:
        check(f"live send failed: {e}", False)
else:
    print("\nTest 6: Live hub send skipped (run with --live to enable)")


# ── Summary ───────────────────────────────────────────────────────────────────
print("\n" + "-" * 40)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"Results: {passed}/{total} passed")
if passed < total:
    print("FAILED tests:")
    for name, ok in results:
        if not ok:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("All tests passed.")
