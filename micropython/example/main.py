import network
import time
import logfire

WIFI_SSID = "Your_SSID"
WIFI_PASS = "Your_Password"
LOGFIRE_HOST = "10.0.0.XX"
LOGFIRE_PORT = 1880

def connect_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        wlan.connect(WIFI_SSID, WIFI_PASS)
        print("Connecting to WiFi", end="")
        while not wlan.isconnected():
            print(".", end="")
            time.sleep(0.5)
        print(" connected!")
    return wlan


wlan = connect_wifi()

logfire.init("MyPico", LOGFIRE_HOST, LOGFIRE_PORT)
logfire.log("Device booted")
print("Device booted")

counter = 0
while True:
    time.sleep(5)
    counter += 1
    if not wlan.isconnected():
        print("WiFi lost, reconnecting...")
        wlan = connect_wifi()
    logfire.log("Heartbeat #" + str(counter))
    print("Heartbeat #" + str(counter))
