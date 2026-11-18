var requestBody = msg.payload;

if (typeof requestBody === "string") {
    try {
        requestBody = JSON.parse(requestBody);
    } catch (error) {
        requestBody = null;
    }
}

var device =
    requestBody && typeof requestBody.device === "string"
        ? requestBody.device.trim()
        : "";

if (!device) {
    msg.statusCode = 400;
    msg.headers = { "content-type": "text/plain; charset=utf-8" };
    msg.payload = "Missing device";
    return [msg, null];
}

if (flow.get("logfireReady") !== true) {
    msg.statusCode = 503;
    msg.headers = { "content-type": "text/plain; charset=utf-8" };
    msg.payload = "Log store is starting";
    return [msg, null];
}

var logs = flow.get("logs") || {};
delete logs[device];
flow.set("logs", logs);

// Preserve msg.req/msg.res from the HTTP In node for HTTP Response.
msg.statusCode = 200;
msg.headers = { "content-type": "text/plain; charset=utf-8" };
msg.payload = "OK";

var fileMessage = { payload: JSON.stringify(logs) };
return [msg, fileMessage];
