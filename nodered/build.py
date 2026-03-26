"""
Build script for LogFire.
Reads index.html and embeds it into flow.json
so the flow serves the UI directly at GET /logfire.

Usage: python build.py  (run from nodered/ folder)
"""

import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(DIR, "logfireUI.html")
FLOW_PATH = os.path.join(DIR, "flow.json")
SERVE_NODE_ID = "fn_serve_ui"


def build():
    with open(HTML_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    with open(FLOW_PATH, "r", encoding="utf-8") as f:
        flow = json.load(f)

    # Escape for JS template literal: backticks and ${
    html_escaped = html.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    js_code = "msg.payload = `" + html_escaped + "`;\nmsg.headers = { 'content-type': 'text/html' };\nreturn msg;"

    found = False
    for node in flow:
        if node.get("id") == SERVE_NODE_ID:
            node["func"] = js_code
            found = True
            break

    if not found:
        print(f"ERROR: node '{SERVE_NODE_ID}' not found in flow.json")
        return False

    with open(FLOW_PATH, "w", encoding="utf-8") as f:
        json.dump(flow, f, indent=4, ensure_ascii=False)

    print(f"OK: embedded {len(html)} bytes of HTML into {FLOW_PATH}")
    return True


if __name__ == "__main__":
    build()
