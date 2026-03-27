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


def init(device_name, host, port=1880):
    global _device_name, _host, _port
    _device_name = device_name
    _host = host
    _port = port


def mirror_serial(enable):
    global _mirror
    _mirror = enable


def log(message, level=0):
    if _mirror:
        if level > 0 and level in _LEVEL_NAMES:
            print("[{}] {}".format(_LEVEL_NAMES[level], message))
        else:
            print(message)

    if _host is None:
        return
    s = None
    try:
        gc.collect()
        if level > 0:
            payload = "{}(-{}): {}".format(_device_name, level, message)
        else:
            payload = "{}: {}".format(_device_name, message)
        addr = socket.getaddrinfo(_host, _port)[0][-1]
        s = socket.socket()
        s.settimeout(5)
        s.connect(addr)
        request = (
            "POST /log HTTP/1.1\r\n"
            "Host: {}:{}\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: {}\r\n"
            "\r\n"
            "{}"
        ).format(_host, _port, len(payload), payload)
        s.send(request.encode())
        s.recv(64)
    except:
        pass
    finally:
        if s:
            try:
                s.close()
            except:
                pass
