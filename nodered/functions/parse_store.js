var MAX_BYTES_PER_DEVICE = 3 * 1024 * 1024;
var raw = msg.payload;

function reject(message) {
    if (!msg.res) {
        return [null, null];
    }

    msg.statusCode = 400;
    msg.headers = { "content-type": "text/plain; charset=utf-8" };
    msg.payload = message;
    return [msg, null];
}

function entryBytes(entry) {
    // Same measure as the size-limit and restore functions: JSON + separator.
    return Buffer.byteLength(JSON.stringify(entry), "utf8") + 1;
}

if (typeof raw !== "string") {
    return reject("Bad format. Expected DEVICE: message");
}

// Senders like println() or nc add a trailing newline; it is not part of the message.
raw = raw.replace(/[\r\n]+$/, "");

if (raw.indexOf(":") === -1) {
    return reject("Bad format. Expected DEVICE: message");
}

var level = 0;
var device;
var message;
// The device name and level are on the first line; the message may span lines.
var match = raw.match(/^([^\r\n]+?)\(-(\d)\):[ \t]*([\s\S]*)$/);

if (match) {
    device = match[1].trim();
    var parsedLevel = parseInt(match[2], 10);
    if (parsedLevel >= 1 && parsedLevel <= 4) {
        level = parsedLevel;
    }
    message = match[3];
} else {
    var separatorIndex = raw.indexOf(":");
    device = raw.substring(0, separatorIndex).trim();
    message = raw.substring(separatorIndex + 1).trim();
}

var reservedDeviceNames = ["__proto__", "constructor", "prototype"];

if (
    !device ||
    device.length > 64 ||
    /[\u0000-\u001f\u007f]/.test(device) ||
    reservedDeviceNames.indexOf(device) !== -1
) {
    return reject("Invalid device name");
}

var timestamp = new Date().toISOString();
var sequence = (context.get("entrySequence") || 0) + 1;
if (sequence > 999999) {
    sequence = 1;
}
context.set("entrySequence", sequence);

var entry = {
    id: timestamp + "-" + ("000000" + sequence).slice(-6),
    device: device,
    message: message,
    timestamp: timestamp,
    level: level
};

if (flow.get("logfireReady") === true) {
    var logs = flow.get("logs") || {};
    var logBytes = flow.get("logBytes") || {};

    if (!Object.prototype.hasOwnProperty.call(logs, device)) {
        logs[device] = [];
        logBytes[device] = 0;
    }
    logs[device].push(entry);
    logBytes[device] = (logBytes[device] || 0) + entryBytes(entry);

    // Enforce the per-device cap on every insert, oldest entries first.
    while (logBytes[device] > MAX_BYTES_PER_DEVICE && logs[device].length > 1) {
        logBytes[device] -= entryBytes(logs[device].shift());
    }

    flow.set("logs", logs);
    flow.set("logBytes", logBytes);
    flow.set("logsDirty", true);   // persisted by "Save logs" (atomic, at most every 2 s)
} else {
    // Startup: buffer until "Restore to context" has merged the saved file.
    var pending = flow.get("pendingLogs") || {};
    if (!Object.prototype.hasOwnProperty.call(pending, device)) {
        pending[device] = [];
    }
    pending[device].push(entry);
    flow.set("pendingLogs", pending);
}

var httpMessage = null;
if (msg.res) {
    // Preserve msg.req/msg.res from the HTTP In node for HTTP Response.
    msg.statusCode = 200;
    msg.headers = { "content-type": "text/plain; charset=utf-8" };
    msg.payload = "OK";
    httpMessage = msg;
}

return [httpMessage, { payload: entry }];
