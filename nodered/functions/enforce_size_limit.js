var logs = flow.get("logs") || {};
var maxBytesPerDevice = 3 * 1024 * 1024;
var deviceNames = Object.keys(logs);
var changed = false;

for (var i = 0; i < deviceNames.length; i++) {
    var device = deviceNames[i];
    var entries = logs[device];

    if (!Array.isArray(entries)) {
        delete logs[device];
        changed = true;
        continue;
    }

    var size = Buffer.byteLength(JSON.stringify(entries), "utf8");
    while (size > maxBytesPerDevice && entries.length > 0) {
        size -= Buffer.byteLength(JSON.stringify(entries[0]), "utf8") + 1;
        entries.shift();
        changed = true;
    }

    if (entries.length === 0) {
        delete logs[device];
        changed = true;
    }
}

if (changed) {
    flow.set("logs", logs);
}

msg.payload = JSON.stringify(logs);
return msg;
