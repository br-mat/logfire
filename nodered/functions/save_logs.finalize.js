// Invalidate any older asynchronous save before publishing the final snapshot.
// This synchronous flush completes before the Function node's stop hook returns.
var state = context.get("logfireSaveState");
if (state) {
    state.stopping = true;
}

if (
    flow.get("logfireReady") === true &&
    (flow.get("logsDirty") === true || (state && state.saving))
) {
    var FILE = "/data/logfire_logs.json";
    var temporaryDirectory;
    try {
        var data = JSON.stringify(flow.get("logs") || {});
        temporaryDirectory = fs.mkdtempSync(FILE + ".tmp-");
        var temporaryFile = temporaryDirectory + "/snapshot";
        var descriptor = fs.openSync(temporaryFile, "w");
        try {
            fs.writeFileSync(descriptor, data, "utf8");
            fs.fsyncSync(descriptor);
        } finally {
            fs.closeSync(descriptor);
        }
        fs.renameSync(temporaryFile, FILE);
        flow.set("logsDirty", false);
    } catch (error) {
        flow.set("logsDirty", true);
        node.error("LogFire: final save failed: " + error.message);
    } finally {
        if (temporaryDirectory) {
            try {
                fs.unlinkSync(temporaryDirectory + "/snapshot");
            } catch (error) {
                if (error.code !== "ENOENT") {
                    node.warn("LogFire: temp cleanup failed: " + error.message);
                }
            }
            try {
                fs.rmdirSync(temporaryDirectory);
            } catch (error) {
                node.warn("LogFire: temp cleanup failed: " + error.message);
            }
        }
    }
}
