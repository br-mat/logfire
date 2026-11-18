"""Embed the maintained UI and Function-node sources into flow.json.

Usage from the repository root:
    python nodered/build.py
"""

import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))
HTML_PATH = os.path.join(DIR, "logfireUI.html")
FLOW_PATH = os.path.join(DIR, "flow.json")
SERVE_NODE_ID = "fn_serve_ui"
FUNCTION_SOURCES = {
    "fn_parse_store": "parse_store.js",
    "fn_list_devices": "list_devices.js",
    "fn_get_logs": "get_logs.js",
    "fn_clear_device": "clear_device.js",
    "fn_auto_delete": "enforce_size_limit.js",
    "fn_restore_logs": "restore_logs.js",
}
FUNCTION_INITIALIZERS = {
    "fn_parse_store": "parse_store.initialize.js",
}
NODE_OVERRIDES = {
    "file_read": {
        "sendError": True,
    },
    "fn_restore_logs": {
        "outputs": 1,
        "wires": [["file_save"]],
    },
}


def read_text(path):
    with open(path, "r", encoding="utf-8") as source_file:
        return source_file.read()


def build():
    html = read_text(HTML_PATH)

    with open(FLOW_PATH, "r", encoding="utf-8") as f:
        flow = json.load(f)

    # Escape for JS template literal: backticks and ${
    html_escaped = html.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    js_code = (
        "msg.payload = `"
        + html_escaped
        + "`;\n"
        + "msg.headers = {\n"
        + "    'content-type': 'text/html; charset=utf-8',\n"
        + "    'cache-control': 'no-store'\n"
        + "};\n"
        + "return msg;"
    )

    remaining_function_ids = set(FUNCTION_SOURCES)
    remaining_initializer_ids = set(FUNCTION_INITIALIZERS)
    remaining_override_ids = set(NODE_OVERRIDES)
    serve_node_found = False
    for node in flow:
        if node.get("id") == SERVE_NODE_ID:
            node["func"] = js_code
            serve_node_found = True

        node_id = node.get("id")
        if node_id in FUNCTION_SOURCES:
            source_path = os.path.join(DIR, "functions", FUNCTION_SOURCES[node_id])
            node["func"] = read_text(source_path).rstrip()
            remaining_function_ids.remove(node_id)

        if node_id in FUNCTION_INITIALIZERS:
            source_path = os.path.join(
                DIR,
                "functions",
                FUNCTION_INITIALIZERS[node_id],
            )
            node["initialize"] = read_text(source_path).rstrip()
            remaining_initializer_ids.remove(node_id)

        if node_id in NODE_OVERRIDES:
            node.update(NODE_OVERRIDES[node_id])
            remaining_override_ids.remove(node_id)

    if not serve_node_found:
        print(f"ERROR: node '{SERVE_NODE_ID}' not found in flow.json")
        return False

    if remaining_function_ids:
        missing = ", ".join(sorted(remaining_function_ids))
        print(f"ERROR: function nodes not found in flow.json: {missing}")
        return False

    if remaining_initializer_ids:
        missing = ", ".join(sorted(remaining_initializer_ids))
        print(f"ERROR: initializer nodes not found in flow.json: {missing}")
        return False

    if remaining_override_ids:
        missing = ", ".join(sorted(remaining_override_ids))
        print(f"ERROR: override nodes not found in flow.json: {missing}")
        return False

    temporary_flow_path = FLOW_PATH + ".tmp"
    try:
        with open(temporary_flow_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(flow, f, indent=2, ensure_ascii=False)
            f.write("\n")
        os.replace(temporary_flow_path, FLOW_PATH)
    finally:
        if os.path.exists(temporary_flow_path):
            os.remove(temporary_flow_path)

    print(
        f"OK: embedded {len(html)} bytes of HTML and "
        f"{len(FUNCTION_SOURCES)} function sources plus "
        f"{len(FUNCTION_INITIALIZERS)} initializer into {FLOW_PATH}"
    )
    return True


if __name__ == "__main__":
    raise SystemExit(0 if build() else 1)
