var logs = flow.get("logs") || {};
msg.payload = Object.keys(logs);
return msg;
