"""
LogFire — lightweight debug logging for MicroPython.
Works on Raspberry Pi Pico W and Pico W2.

Usage:
    import logfire
    logfire.init("MyPico", "10.0.0.XX")
    logfire.log("Device booted")
    logfire.log("Low battery", 2)   # 0=plain 1=INFO 2=WARN 3=ERROR 4=CRITICAL
    logfire.mirror_serial(False)    # disable Serial mirroring (on by default)
"""

import socket
import gc

_LEVEL_NAMES = {1: "INFO", 2: "WARN", 3: "ERROR", 4: "CRITICAL"}

_device_name = None
_host = None
_port = None
_mirror = True
_sock = None
_connected = False


def init(device_name, host, port=1880):
    global _device_name, _host, _port
    _device_name = device_name
    _host = host
    _port = port


def mirror_serial(enable):
    global _mirror
    _mirror = enable


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
        except:
            pass
    _sock = None
    _connected = False


def log(message, level=0):
    global _connected
    if _mirror:
        if level > 0 and level in _LEVEL_NAMES:
            print("[{}] {}".format(_LEVEL_NAMES[level], message))
        else:
            print(message)

    if _host is None:
        return

    try:
        _ensure_connected()

        if level > 0:
            payload = "{}(-{}): {}".format(_device_name, level, message)
        else:
            payload = "{}: {}".format(_device_name, message)

        request = (
            "POST /log HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: {}\r\n"
            "Connection: keep-alive\r\n"
            "\r\n"
            "{}"
        ).format(_host, _port, len(payload), payload)
        _sock.send(request.encode())
        _sock.recv(64)
    except:
        _disconnect()
