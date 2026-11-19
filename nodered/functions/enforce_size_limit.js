// Safety net, every 60 s: recompute exact per-device sizes and trim.
// The cap itself is enforced on insert by "Parse & Store".
var MAX_BYTES_PER_DEVICE = 3 * 1024 * 1024;

if (flow.get("logfireReady") !== true) {
    return null;
}

var logs = flow.get("logs") || {};
var logBytes = {};
var deviceNames = Object.keys(logs);
var changed = false;

function entryBytes(entry) {
    return Buffer.byteLength(JSON.stringify(entry), "utf8") + 1;
}

for (var i = 0; i < deviceNames.length; i++) {
    var device = deviceNames[i];
    var entries = logs[device];

    if (!Array.isArray(entries) || entries.length === 0) {
        delete logs[device];
        changed = true;
        continue;
    }

    var size = 0;
    for (var j = 0; j < entries.length; j++) {
        size += entryBytes(entries[j]);
    }
    while (size > MAX_BYTES_PER_DEVICE && entries.length > 1) {
        size -= entryBytes(entries.shift());
        changed = true;
    }
    logBytes[device] = size;
}

flow.set("logBytes", logBytes);
if (changed) {
    flow.set("logs", logs);
    flow.set("logsDirty", true);
}
return null;
