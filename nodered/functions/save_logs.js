// Save a snapshot off the message path. Separate temporary files prevent an
// old open handle from modifying a newer snapshot published during shutdown.
var FILE = "/data/logfire_logs.json";
var state = context.get("logfireSaveState");

if (
    !state || state.stopping || state.saving ||
    flow.get("logfireReady") !== true || flow.get("logsDirty") !== true
) {
    return null;
}

state.saving = true;
flow.set("logsDirty", false);

(async function () {
    var temporaryDirectory;
    try {
        var data = JSON.stringify(flow.get("logs") || {});
        temporaryDirectory = await fs.promises.mkdtemp(FILE + ".tmp-");
        var temporaryFile = temporaryDirectory + "/snapshot";
        var handle = await fs.promises.open(temporaryFile, "w");
        try {
            await handle.writeFile(data, "utf8");
            await handle.sync();
        } finally {
            await handle.close();
        }
        // No await between the check and rename: finalization cannot interleave
        // here. Bulk writing/fsync stays async; only the rename is synchronous.
        if (!state.stopping) {
            fs.renameSync(temporaryFile, FILE);
        }
    } catch (error) {
        // The finalizer handles the current snapshot once stopping starts.
        if (!state.stopping) {
            flow.set("logsDirty", true);
        }
        node.error("LogFire: saving logs failed: " + error.message);
    } finally {
        if (temporaryDirectory) {
            try {
                await fs.promises.unlink(temporaryDirectory + "/snapshot");
            } catch (error) {
                if (error.code !== "ENOENT") {
                    node.warn("LogFire: temp cleanup failed: " + error.message);
                }
            }
            try {
                await fs.promises.rmdir(temporaryDirectory);
            } catch (error) {
                node.warn("LogFire: temp cleanup failed: " + error.message);
            }
        }
        state.saving = false;
    }
})();

return null;
