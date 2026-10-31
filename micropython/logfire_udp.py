"""
LogFire UDP — lightweight debug logging for MicroPython over UDP.
Works on Raspberry Pi Pico W and Pico W2.

Usage:
    import logfire_udp
    logfire_udp.init("MyPico", "10.0.0.XX")
    logfire_udp.log("Device booted")
    logfire_udp.log("Low battery", 2)   # 0=plain 1=INFO 2=WARN 3=ERROR 4=CRITICAL
    logfire_udp.mirror_serial(False)    # disable Serial mirroring (on by default)
    logfire_udp.local_only(True)        # Serial only, skip all network I/O
"""

import socket

_LEVEL_NAMES = {1: "INFO", 2: "WARN", 3: "ERROR", 4: "CRITICAL"}

_device_name = None
_host = None
_port = None
_mirror = True
_local_only = False
_sock = None


def init(device_name, host, port=1880):
    global _device_name, _host, _port, _sock
    if _sock is not None:
        try:
            _sock.close()
        except OSError:
            pass
        _sock = None
    _device_name = device_name
    _host = host
    _port = port
    _sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


def mirror_serial(enable):
    global _mirror
    _mirror = enable


def local_only(enable):
    global _local_only
    _local_only = enable


def log(message, level=0):
    if _mirror:
        if level > 0 and level in _LEVEL_NAMES:
            print("[{}] {}".format(_LEVEL_NAMES[level], message))
        else:
            print(message)

    if _local_only or _host is None:
        return

    if level > 0:
        payload = "{}(-{}): {}".format(_device_name, level, message)
    else:
        payload = "{}: {}".format(_device_name, message)

    try:
        addr = socket.getaddrinfo(_host, _port)[0][-1]
        _sock.sendto(payload.encode(), addr)
    except OSError:
        pass
