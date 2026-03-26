"""
LogFire — lightweight debug logging for MicroPython.
Works on Raspberry Pi Pico W and Pico W2.

Usage:
    import logfire
    logfire.init("MyPico", "10.0.0.XX")
    logfire.log("Device booted")
"""

import socket
import gc

_device_name = None
_host = None
_port = None


def init(device_name, host, port=1880):
    global _device_name, _host, _port
    _device_name = device_name
    _host = host
    _port = port


def log(message):
    if _host is None:
        return
    s = None
    try:
        gc.collect()
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
