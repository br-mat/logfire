var raw = msg.payload;

function reject(message) {
    if (!msg.res) {
        return [null, null, null];
    }

    msg.statusCode = 400;
    msg.headers = { "content-type": "text/plain; charset=utf-8" };
    msg.payload = message;
    return [msg, null, null];
}

if (typeof raw !== "string" || raw.indexOf(":") === -1) {
    return reject("Bad format. Expected DEVICE: message");
}

var level = 0;
var device;
var message;
var match = raw.match(/^(.+?)\(-(\d)\):\s*(.*)$/);

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

var storeIsReady = flow.get("logfireReady") === true;
var targetStore = storeIsReady
    ? flow.get("logs") || {}
    : flow.get("pendingLogs") || {};

if (!Object.prototype.hasOwnProperty.call(targetStore, device)) {
    targetStore[device] = [];
}
targetStore[device].push(entry);

if (storeIsReady) {
    flow.set("logs", targetStore);
} else {
    flow.set("pendingLogs", targetStore);
}

var httpMessage = null;
if (msg.res) {
    // Preserve msg.req/msg.res from the HTTP In node for HTTP Response.
    msg.statusCode = 200;
    msg.headers = { "content-type": "text/plain; charset=utf-8" };
    msg.payload = "OK";
    httpMessage = msg;
}

var websocketMessage = { payload: entry };
var fileMessage = storeIsReady
    ? { payload: JSON.stringify(targetStore) }
    : null;

return [httpMessage, websocketMessage, fileMessage];
