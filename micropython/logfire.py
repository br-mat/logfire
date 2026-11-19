"""
LogFire — lightweight debug logging for MicroPython.
Works on Raspberry Pi Pico W and Pico W2.

Usage:
    import logfire
    logfire.init("MyPico", "10.0.0.XX")
    logfire.log("Device booted")
    logfire.log("Low battery", 2)   # 0=plain 1=INFO 2=WARN 3=ERROR 4=CRITICAL
    logfire.mirror_serial(False)    # disable Serial mirroring (on by default)
    logfire.local_only(True)        # Serial only, skip all network I/O
"""

import socket
import gc

try:
    from time import ticks_ms, ticks_diff
except ImportError:  # CPython (tests): emulate MicroPython's tick helpers
    from time import monotonic as _monotonic

    def ticks_ms():
        return int(_monotonic() * 1000)

    def ticks_diff(new, old):
        return new - old

_LEVEL_NAMES = {1: "INFO", 2: "WARN", 3: "ERROR", 4: "CRITICAL"}

# The hub (Node.js) closes idle keep-alive connections after 5 s. Reconnect
# before that instead of writing into a connection the hub already closed.
_IDLE_RECONNECT_MS = 4000
_MAX_HEADER_BYTES = 1024

_device_name = None
_host = None
_port = None
_mirror = True
_local_only = False
_sock = None
_connected = False
_last_used = 0


def init(device_name, host, port=1880):
    global _device_name, _host, _port
    _disconnect()
    _device_name = device_name
    _host = host
    _port = port


def mirror_serial(enable):
    global _mirror
    _mirror = enable


def local_only(enable):
    global _local_only
    _local_only = enable
    if enable:
        _disconnect()


def _ensure_connected():
    global _sock, _connected
    if _connected:
        return
    gc.collect()
    addr = socket.getaddrinfo(_host, _port)[0][-1]
    _sock = socket.socket()
    _sock.settimeout(5)
    _sock.connect(addr)
    _connected = True


def _disconnect():
    global _sock, _connected
    if _sock:
        try:
            _sock.close()
        except OSError:
            pass
    _sock = None
    _connected = False


def _send_all(data):
    # MicroPython sockets may lack sendall(); write() sends everything on a
    # blocking socket. CPython sockets (tests) have sendall() but no write().
    if hasattr(_sock, "sendall"):
        _sock.sendall(data)
    else:
        _sock.write(data)


def _recv_some(size):
    data = _sock.recv(size)
    if not data:
        raise OSError("connection closed by hub")
    return data


def _read_response():
    """Read one complete HTTP response so nothing is left in the socket.

    Returns True when the hub keeps the connection open for the next request.
    """
    buf = b""
    while b"\r\n\r\n" not in buf:
        buf += _recv_some(256)
        if len(buf) > _MAX_HEADER_BYTES:
            raise OSError("response header too large")
    head, _, body = buf.partition(b"\r\n\r\n")
    length = 0
    keep_alive = True
    for line in head.split(b"\r\n")[1:]:
        name, _, value = line.partition(b":")
        name = name.strip().lower()
        if name == b"content-length":
            length = int(value.strip().decode())
        elif name == b"connection" and value.strip().lower() == b"close":
            keep_alive = False
    while len(body) < length:
        body += _recv_some(length - len(body))
    return keep_alive


def _format(message, level):
    if level > 0:
        return "{}(-{}): {}".format(_device_name, level, message)
    return "{}: {}".format(_device_name, message)


def log(message, level=0):
    global _last_used
    if _mirror:
        if level > 0 and level in _LEVEL_NAMES:
            print("[{}] {}".format(_LEVEL_NAMES[level], message))
        else:
            print(message)

    if _local_only or _host is None:
        return

    body = _format(message, level).encode('utf-8')
    request = (
        "POST /log HTTP/1.1\r\n"
        "Host: {}:{}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "Content-Length: {}\r\n"
        "Connection: keep-alive\r\n"
        "\r\n"
    ).format(_host, _port, len(body)).encode('utf-8') + body

    if _connected and ticks_diff(ticks_ms(), _last_used) > _IDLE_RECONNECT_MS:
        _disconnect()

    # A reused connection may have been closed by the hub in the meantime:
    # then reconnect and send once more. A fresh connection that fails means
    # the hub is unreachable; give up instead of waiting for a second timeout.
    for _ in range(2):
        reused = _connected
        try:
            _ensure_connected()
            _send_all(request)
            keep_alive = _read_response()
            _last_used = ticks_ms()
            if not keep_alive:
                _disconnect()
            return
        except OSError:
            _disconnect()
            if not reused:
                return
