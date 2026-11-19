var restoredLogs = {};
var savedDataWasValid = false;

try {
    var parsedLogs = JSON.parse(msg.payload);
    if (!parsedLogs || Array.isArray(parsedLogs) || typeof parsedLogs !== "object") {
        throw new Error("Saved log data is not an object");
    }
    restoredLogs = parsedLogs;
    savedDataWasValid = true;
} catch (error) {
    node.warn("LogFire: no valid saved logs found, starting fresh");
}

var mergedLogs = Object.create(null);
var seenEntries = Object.create(null);

function mergeStore(store) {
    if (!store || Array.isArray(store) || typeof store !== "object") {
        return;
    }

    var deviceNames = Object.keys(store);
    for (var i = 0; i < deviceNames.length; i++) {
        var device = deviceNames[i];
        var entries = store[device];
        if (!Array.isArray(entries)) {
            continue;
        }

        if (!mergedLogs[device]) {
            mergedLogs[device] = [];
        }

        for (var j = 0; j < entries.length; j++) {
            var entry = entries[j];
            if (!entry || typeof entry !== "object") {
                continue;
            }

            var key = entry.id
                ? "id:" + entry.id
                : "legacy:" +
                  JSON.stringify([
                      entry.device,
                      entry.timestamp,
                      entry.level,
                      entry.message
                  ]);

            if (!seenEntries[key]) {
                seenEntries[key] = true;
                mergedLogs[device].push(entry);
            }
        }
    }
}

// Current context can survive a flow deploy; pending logs cover a clean restart.
mergeStore(restoredLogs);
mergeStore(flow.get("logs"));
mergeStore(flow.get("pendingLogs"));

var mergedDeviceNames = Object.keys(mergedLogs);
for (var i = 0; i < mergedDeviceNames.length; i++) {
    var deviceEntries = mergedLogs[mergedDeviceNames[i]];
    deviceEntries.sort(function (left, right) {
        return String(left.timestamp || "").localeCompare(
            String(right.timestamp || "")
        );
    });
}

// Apply the per-device cap and record sizes for "Parse & Store".
var MAX_BYTES_PER_DEVICE = 3 * 1024 * 1024;
var logBytes = Object.create(null);
function entryBytes(entry) {
    return Buffer.byteLength(JSON.stringify(entry), "utf8") + 1;
}
for (var k = 0; k < mergedDeviceNames.length; k++) {
    var name = mergedDeviceNames[k];
    var list = mergedLogs[name];
    var size = 0;
    for (var m = 0; m < list.length; m++) {
        size += entryBytes(list[m]);
    }
    while (size > MAX_BYTES_PER_DEVICE && list.length > 1) {
        size -= entryBytes(list.shift());
    }
    logBytes[name] = size;
}

flow.set("logs", mergedLogs);
flow.set("logBytes", logBytes);
flow.set("pendingLogs", {});
flow.set("logsDirty", true);   // persist the merged store via "Save logs"
flow.set("logfireReady", true);

if (savedDataWasValid) {
    node.warn(
        "LogFire: restored " +
            Object.keys(restoredLogs).length +
            " devices from file"
    );
}

return null;
