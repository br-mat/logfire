"""
LogFire test script — development use only.

Verifies logfire.py (TCP) and logfire_udp.py (UDP) on standard CPython (no Pico needed).
Not intended for deployment — the example/ folder contains the usage reference.

TCP Tests:
  1.  local_only skips DNS and socket creation (mock proof)
  2.  local_only stdout format (captured and verified)
  3.  mirror_serial=False produces no output (captured and verified)
  4.  local_only=False restores normal network path (mock proof)
  5.  local_only(True) disconnects existing socket (state check)

UDP Tests:
  6.  local_only skips sendto (proved by mock socket)
  7.  local_only stdout format (captured and verified)
  8.  mirror_serial=False produces no output (captured and verified)
  9.  local_only(False) clears flag (state check)
  10. socket created at init() (state check)
       Reinitialization closes the previous socket; loopback verifies all levels.

Live Tests (--live only, requires hub at LOGFIRE_HOST:LOGFIRE_PORT):
  11. TCP: sends 4 levels to pylog-tcp, verifies all arrived on hub via /logs
  12. UDP: same to pylog-udp (requires UDP port 1880 to be reachable)

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
import socket
from unittest.mock import patch

# ── Helpers ───────────────────────────────────────────────────────────────────

def fresh():
    """Reset TCP module state between tests."""
    if "logfire" in sys.modules:
        sys.modules["logfire"]._disconnect()
        del sys.modules["logfire"]
    import logfire
    return logfire

def fresh_udp():
    """Reset UDP module state between tests."""
    if "logfire_udp" in sys.modules:
        sock = sys.modules["logfire_udp"]._sock
        if sock is not None:
            sock.close()
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

# Test 1: local_only skips network (mock proof)
print("\nTest 1: local_only skips network entirely (TCP)")
lf = fresh()
lf.init("TestDevice", "127.0.0.1", 1880)
lf.local_only(True)
lf.mirror_serial(False)

with patch.object(socket, "getaddrinfo") as resolve, patch.object(socket, "socket") as create:
    for _ in range(10):
        lf.log("local only", 1)
    check("local_only skips DNS and socket creation", not resolve.called and not create.called)


# Test 2: local_only stdout format (TCP)
print("\nTest 2: local_only stdout format (TCP)")
lf = fresh()
lf.init("TestDevice", "127.0.0.1", 1880)
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

addr = ("127.0.0.1", 1880)
with patch.object(socket, "getaddrinfo", return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", addr)]), patch.object(socket, "socket") as create:
    lf.local_only(False)
    lf.log("now tries network")
    sock = create.return_value
    check("network path reconnects after local_only(False)", sock.connect.call_args is not None and sock.connect.call_args.args == (addr,))
    check("restored network path sends the log", sock.send.called and b"now tries network" in sock.send.call_args.args[0])


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
    def close(self):
        pass


# Test 6: local_only skips sendto (mock proof, UDP)
# UDP sendto() returns instantly even to unreachable hosts, so timing cannot
# prove the network path was skipped. A mock socket is used instead.
print("\nTest 6: local_only skips sendto entirely (UDP)")
lf = fresh_udp()
lf.init("TestDevice", "10.0.255.254", 1880)
lf.mirror_serial(False)

import logfire_udp as _lf_udp_mod
mock = MockSock()
_lf_udp_mod._sock.close()
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


print("\nUDP socket reinitialization")
old_sock = lf._sock
lf.init("NewDevice", "127.0.0.1", 1880)
check("reinitialization closes the old socket", old_sock.fileno() == -1)
check("reinitialization creates a usable replacement", lf._sock.fileno() >= 0)


print("\nUDP loopback delivery")
lf = fresh_udp()
lf.mirror_serial(False)
with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(1)
    lf.init("Loopback", "127.0.0.1", receiver.getsockname()[1])
    for level in range(5):
        message = "temperature: 23\u00b0C"
        lf.log(message, level)
        prefix = "Loopback(-{})".format(level) if level else "Loopback"
        expected = "{}: {}".format(prefix, message).encode("utf-8")
        try:
            received = receiver.recvfrom(4096)[0]
        except socket.timeout:
            received = None
        check("UTF-8 datagram delivered at level {}".format(level), received == expected)
lf._sock.close()


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
    print("  Requires UDP port 1880 to be reachable on the hub")
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
