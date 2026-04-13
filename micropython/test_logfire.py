"""
LogFire test script — development use only.

Verifies logfire.py (TCP) and logfire_udp.py (UDP) on standard CPython (no Pico needed).
Not intended for deployment — the example/ folder contains the usage reference.

TCP Tests:
  1.  local_only skips network (proved by timing against unreachable host)
  2.  local_only stdout format (captured and verified)
  3.  mirror_serial=False produces no output (captured and verified)
  4.  local_only=False restores normal network path (timing proof)
  5.  local_only(True) disconnects existing socket (state check)

UDP Tests:
  6.  local_only skips sendto (proved by mock socket)
  7.  local_only stdout format (captured and verified)
  8.  mirror_serial=False produces no output (captured and verified)
  9.  local_only(False) clears flag (state check)
  10. socket created at init() (state check)

Live Tests (--live only, requires hub at LOGFIRE_HOST:LOGFIRE_PORT):
  11. TCP: sends 4 levels to pylog-tcp, verifies all arrived on hub via /logs
  12. UDP: same to pylog-udp — expected failure until Node-RED UDP listener is in flow

Usage:
  python test_logfire.py           # runs unit tests only
  python test_logfire.py --live    # also runs live hub delivery verification
"""

LOGFIRE_HOST = "10.0.0.XX"   # set to your hub's IP before running --live
LOGFIRE_PORT = 1880

import sys
import io
import time
import urllib.request
import json

# ── Helpers ───────────────────────────────────────────────────────────────────

def fresh():
    """Reset TCP module state between tests."""
    if "logfire" in sys.modules:
        del sys.modules["logfire"]
    import logfire
    return logfire

def fresh_udp():
    """Reset UDP module state between tests."""
    if "logfire_udp" in sys.modules:
        del sys.modules["logfire_udp"]
    import logfire_udp
    return logfire_udp

def capture(fn):
    """Run fn() with stdout redirected, return what was printed."""
    buf = io.StringIO()
    old = sys.stdout
    sys.stdout = buf
    try:
        fn()
    finally:
        sys.stdout = old
    return buf.getvalue()

results = []

def check(name, ok):
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {name}")
    results.append((name, ok))

def fetch_device_logs(device):
    """Fetch all log entries for a device from the hub. Returns list or None on error."""
    try:
        r = urllib.request.urlopen(
            f"http://{LOGFIRE_HOST}:{LOGFIRE_PORT}/logs",
            timeout=5
        )
        all_logs = json.loads(r.read().decode())
        return all_logs.get(device, [])
    except Exception as e:
        print(f"  [!] Could not fetch hub logs: {e}")
        return None

def verify_delivery(tag, device, expected_levels, wait=1.0):
    """
    Wait briefly, fetch /logs, then check that messages containing tag
    arrived at the expected levels. Returns list of (level, arrived) tuples.
    tag must be transport-specific (e.g. "tcp-1234567" vs "udp-1234567")
    so TCP and UDP messages don't cross-match on the same device.
    """
    time.sleep(wait)
    entries = fetch_device_logs(device)
    if entries is None:
        return [(lvl, False) for lvl in expected_levels]
    results_per_level = []
    for lvl in expected_levels:
        found = any(
            tag in e.get("message", "") and e.get("level") == lvl
            for e in entries
        )
        results_per_level.append((lvl, found))
    return results_per_level


# ── TCP Unit Tests ─────────────────────────────────────────────────────────────

# Test 1: local_only skips network (timing proof)
print("\nTest 1: local_only skips network entirely (TCP)")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)  # routable but unreachable
lf.local_only(True)
lf.mirror_serial(False)

t0 = time.time()
for _ in range(10):
    lf.log("should be instant", 1)
elapsed = time.time() - t0
# If local_only is broken and tries to connect, it would stall for seconds.
check("10 log() calls complete in <0.1s with unreachable host", elapsed < 0.1)


# Test 2: local_only stdout format (TCP)
print("\nTest 2: local_only stdout format (TCP)")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.local_only(True)

out = capture(lambda: (
    lf.log("plain message"),
    lf.log("info message", 1),
    lf.log("warn message", 2),
    lf.log("error message", 3),
    lf.log("critical message", 4),
))
check("plain message printed bare (no prefix)", "plain message" in out and "[" not in out.split("plain message")[0].split("\n")[-1])
check("[INFO] prefix on level 1",     "[INFO] info message" in out)
check("[WARN] prefix on level 2",     "[WARN] warn message" in out)
check("[ERROR] prefix on level 3",    "[ERROR] error message" in out)
check("[CRITICAL] prefix on level 4", "[CRITICAL] critical message" in out)


# Test 3: mirror_serial=False produces no output (TCP)
print("\nTest 3: mirror_serial=False produces no output (TCP)")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)
lf.local_only(True)

out = capture(lambda: lf.log("this must be silent"))
check("no output when mirror_serial=False", out == "")


# Test 4: local_only(False) restores network path (TCP)
print("\nTest 4: local_only(False) re-enables network path (TCP)")
lf = fresh()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.local_only(True)
lf.mirror_serial(False)
lf.log("local only")

lf.local_only(False)
lf.mirror_serial(False)
t0 = time.time()
lf.log("now tries network")   # TCP connect to unreachable host -- will stall/timeout
elapsed = time.time() - t0
check("network path re-enabled after local_only(False) (took >0.5s)", elapsed > 0.5)


# Test 5: local_only(True) disconnects existing socket (TCP)
print("\nTest 5: local_only(True) disconnects existing socket (TCP)")
lf = fresh()
lf.local_only(True)
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)

import logfire as _lf_mod
_lf_mod._connected = True
_lf_mod._sock = None   # no real socket, but _connected flag is set

lf.local_only(True)    # must call _disconnect() and reset the flag
check("_connected reset to False after local_only(True)", not _lf_mod._connected)


# ── UDP Unit Tests ─────────────────────────────────────────────────────────────

class MockSock:
    """Replaces _sock to detect whether sendto is called."""
    def __init__(self):
        self.called = False
    def sendto(self, data, addr):
        self.called = True


# Test 6: local_only skips sendto (mock proof, UDP)
# UDP sendto() returns instantly even to unreachable hosts, so timing cannot
# prove the network path was skipped. A mock socket is used instead.
print("\nTest 6: local_only skips sendto entirely (UDP)")
lf = fresh_udp()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)

import logfire_udp as _lf_udp_mod
mock = MockSock()
_lf_udp_mod._sock = mock

lf.local_only(True)
lf.log("should not reach sendto", 1)
check("sendto not called when local_only=True", not mock.called)


# Test 7: local_only stdout format (UDP)
print("\nTest 7: local_only stdout format (UDP)")
lf = fresh_udp()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.local_only(True)

out = capture(lambda: (
    lf.log("plain message"),
    lf.log("info message", 1),
    lf.log("warn message", 2),
    lf.log("error message", 3),
    lf.log("critical message", 4),
))
check("plain message printed bare (no prefix)", "plain message" in out and "[" not in out.split("plain message")[0].split("\n")[-1])
check("[INFO] prefix on level 1",     "[INFO] info message" in out)
check("[WARN] prefix on level 2",     "[WARN] warn message" in out)
check("[ERROR] prefix on level 3",    "[ERROR] error message" in out)
check("[CRITICAL] prefix on level 4", "[CRITICAL] critical message" in out)


# Test 8: mirror_serial=False produces no output (UDP)
print("\nTest 8: mirror_serial=False produces no output (UDP)")
lf = fresh_udp()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)
lf.local_only(True)

out = capture(lambda: lf.log("this must be silent"))
check("no output when mirror_serial=False", out == "")


# Test 9: local_only(False) clears flag (UDP)
print("\nTest 9: local_only(False) clears flag (UDP)")
lf = fresh_udp()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.local_only(True)
lf.local_only(False)
import logfire_udp as _lf_udp_mod2
check("_local_only flag cleared", not _lf_udp_mod2._local_only)


# Test 10: socket created at init() (UDP)
print("\nTest 10: socket created at init() (UDP)")
lf = fresh_udp()
import logfire_udp as _lf_udp_mod3
check("_sock is None before init()", _lf_udp_mod3._sock is None)
lf.init("TestDevice", "10.0.255.254", 1880)
check("_sock is not None after init()", _lf_udp_mod3._sock is not None)


# ── Live Delivery Tests ────────────────────────────────────────────────────────

if "--live" not in sys.argv:
    print("\nLive tests skipped (run with --live to enable)")
else:
    RUN_ID = str(int(time.time()))
    LEVELS = [0, 1, 2, 3]
    LEVEL_NAMES = {0: "plain", 1: "INFO", 2: "WARN", 3: "ERROR"}

    # TCP and UDP send to separate devices so they show as distinct tabs in the UI
    # and cannot cross-match during hub verification.
    TCP_DEVICE = "pylog-tcp"
    UDP_DEVICE = "pylog-udp"

    # ── Test 11: TCP live delivery ─────────────────────────────────────────────
    print(f"\nTest 11: TCP live delivery -> {TCP_DEVICE} (run {RUN_ID})")
    lf = fresh()
    lf.init(TCP_DEVICE, LOGFIRE_HOST, LOGFIRE_PORT)
    lf.mirror_serial(False)
    for lvl in LEVELS:
        lf.log(f"tcp-{RUN_ID} {LEVEL_NAMES[lvl]}", lvl)

    print("  Sent 4 messages, fetching hub in 1s...")
    delivered = verify_delivery(f"tcp-{RUN_ID}", TCP_DEVICE, LEVELS)
    for lvl, arrived in delivered:
        check(f"level {lvl} ({LEVEL_NAMES[lvl]}) arrived on hub", arrived)


    # ── Test 12: UDP live delivery ─────────────────────────────────────────────
    print(f"\nTest 12: UDP live delivery -> {UDP_DEVICE} (run {RUN_ID})")
    print("  NOTE: expected failure until Node-RED UDP listener is imported to flow")
    lf = fresh_udp()
    lf.init(UDP_DEVICE, LOGFIRE_HOST, LOGFIRE_PORT)
    lf.mirror_serial(False)
    for lvl in LEVELS:
        lf.log(f"udp-{RUN_ID} {LEVEL_NAMES[lvl]}", lvl)

    print("  Sent 4 messages, fetching hub in 1s...")
    delivered = verify_delivery(f"udp-{RUN_ID}", UDP_DEVICE, LEVELS)
    for lvl, arrived in delivered:
        check(f"UDP level {lvl} ({LEVEL_NAMES[lvl]}) arrived on hub", arrived)


# ── Summary ────────────────────────────────────────────────────────────────────
print("\n" + "-" * 40)
passed = sum(1 for _, ok in results if ok)
total = len(results)
print(f"Results: {passed}/{total} passed")
if passed < total:
    print("Failed:")
    for name, ok in results:
        if not ok:
            print(f"  - {name}")
    sys.exit(1)
else:
    print("All tests passed.")
