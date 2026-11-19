"""Browser test for the LogFire UI (headless Chromium via Playwright).

Covers: history load (/logs), live WebSocket updates (UDP + HTTP sent after page
load), severity filter at all 5 thresholds, console errors, clear button.

Usage:
    pip install -r tests/requirements.txt && playwright install chromium-headless-shell
    python tests/ui_test.py --url http://127.0.0.1:1881 --udp 127.0.0.1:1882 [--screenshot ui.png]
"""
import argparse
import json
import socket
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

ap = argparse.ArgumentParser()
ap.add_argument("--url", required=True)
ap.add_argument("--udp", required=True, help="host:port of the flow's UDP input")
ap.add_argument("--screenshot", default="")
args = ap.parse_args()
BASE = args.url.rstrip("/")
UDP_ADDR = (args.udp.rsplit(":", 1)[0], int(args.udp.rsplit(":", 1)[1]))
DEV = "UiTest"
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{'  -> ' + detail if detail else ''}")


def http_log(text):
    req = urllib.request.Request(f"{BASE}/log", data=text.encode(), method="POST",
                                 headers={"Content-Type": "text/plain; charset=utf-8"})
    urllib.request.urlopen(req, timeout=5).read()


def clear(device):
    req = urllib.request.Request(f"{BASE}/clear", data=json.dumps({"device": device}).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=5).read()


def line(level, n, via):
    prefix = f"{DEV}(-{level})" if level else DEV
    return f"{prefix}: {via} level {level} #{n}"


clear(DEV)
for lvl in range(5):                       # history: 2 per level, before the page opens
    for n in (1, 2):
        http_log(line(lvl, n, "http-history"))

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("dialog", lambda d: d.accept())

    page.goto(f"{BASE}/logfire")
    tab = page.locator(".tab", has_text=DEV)
    tab.wait_for(timeout=10000)
    tab.click()
    panel = page.locator(".log-panel.active")
    lines = panel.locator(".log-line")
    page.wait_for_function("n => document.querySelectorAll('.log-panel.active .log-line').length >= n", arg=10, timeout=10000)
    check("history: 10 entries loaded from /logs", lines.count() == 10, f"{lines.count()} lines")

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    for lvl in range(5):                   # live: 1 per level via UDP after page load
        udp.sendto(line(lvl, 3, "udp-live").encode(), UDP_ADDR)
    try:
        page.wait_for_function("n => document.querySelectorAll('.log-panel.active .log-line').length >= n", arg=15, timeout=10000)
    except Exception:
        pass
    check("live: 5 UDP entries arrived via WebSocket", lines.count() == 15, f"{lines.count()} lines")

    select = panel.locator("select.filter-select")
    names = {0: "ALL", 1: "INFO+", 2: "WARN+", 3: "ERROR+", 4: "CRITICAL"}
    for v in range(5):
        select.select_option(str(v))
        visible = panel.locator(".log-line:not(.level-hidden)")
        expected = 15 if v == 0 else 3 * (5 - v)
        levels = sorted({int(x) for x in visible.evaluate_all("els => els.map(e => e.dataset.level)")})
        check(f"filter {names[v]:8}: {expected} visible, levels {list(range(v, 5)) if v else [0,1,2,3,4]}",
              visible.count() == expected and levels == (list(range(v, 5)) if v else [0, 1, 2, 3, 4]),
              f"{visible.count()} visible, levels {levels}")
        if v == 1:
            check("plain (level 0) lines hidden at INFO+ (dev fix cec73bb)",
                  panel.locator('.log-line[data-level="0"]:not(.level-hidden)').count() == 0)

    select.select_option("0")
    http_log(line(4, 4, "http-live"))      # live via HTTP, filter back to ALL
    try:
        page.wait_for_function("n => document.querySelectorAll('.log-panel.active .log-line').length >= n", arg=16, timeout=10000)
    except Exception:
        pass
    check("live: HTTP entry arrived via WebSocket", lines.count() == 16, f"{lines.count()} lines")
    if args.screenshot:
        page.screenshot(path=args.screenshot, full_page=True)

    panel.locator("button.btn.danger").click()
    time.sleep(1.5)
    devices = json.loads(urllib.request.urlopen(f"{BASE}/devices", timeout=5).read())
    check("clear button removes device on hub", DEV not in devices, f"devices={devices}")
    check("no browser console errors", not errors, "; ".join(errors[:3]))
    browser.close()

print(f"\nResults: {sum(results)}/{len(results)} passed")
sys.exit(0 if all(results) else 1)
