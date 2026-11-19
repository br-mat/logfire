// Deterministic interleavings using the actual Function-node sources.
// The POSIX model preserves inode identity across rename and open handles.
// Usage: node tests/persistence_test.js [path/to/another/source/tree]
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const root = path.resolve(process.argv[2] || path.join(__dirname, '..'));
const dir = path.join(root, 'nodered/functions');
const compile = name => new Function('fs', 'flow', 'context', 'node',
    fs.readFileSync(path.join(dir, name), 'utf8'));
const save = compile('save_logs.js');
const stop = compile('save_logs.finalize.js');
const initialize = fs.existsSync(path.join(dir, 'save_logs.initialize.js'))
    ? compile('save_logs.initialize.js') : () => {};
const FILE = '/data/logfire_logs.json';

function store(initial = {}) {
    const values = new Map(Object.entries(initial));
    return { get: key => values.get(key), set: (key, value) => values.set(key, value) };
}

class FileModel {
    constructor() {
        this.paths = new Map([[FILE, { text: '{"device":["previous"]}' }]]);
        this.directories = new Set();
        this.handles = new Set();
        this.sequence = 0;
        this.failure = null;
        this.gate = null;
        this.promises = {};
        for (const name of ['mkdtemp', 'open', 'unlink', 'rmdir', 'rename']) {
            this.promises[name] = async (...args) => {
                await this.step(name);
                return this[name + 'Sync'](...args);
            };
        }
    }
    fail(name) {
        if (this.failure === name) {
            this.failure = null;
            throw Object.assign(new Error('injected ' + name), { code: 'EIO' });
        }
    }
    pause(name) {
        let release;
        const promise = new Promise(resolve => { release = resolve; });
        this.gate = { name, promise, release, reached: false };
        return this.gate;
    }
    async step(name) {
        if (this.gate && this.gate.name === name && !this.gate.reached) {
            this.gate.reached = true;
            await this.gate.promise;
        }
        this.fail(name);
    }
    mkdtempSync(prefix) {
        this.fail('mkdtempSync');
        const directory = prefix + (++this.sequence);
        this.directories.add(directory);
        return directory;
    }
    openSync(filename) {
        this.fail('openSync');
        // Opening an existing path with "w" truncates that same inode.
        const inode = this.paths.get(filename) || { text: '' };
        inode.text = '';
        this.paths.set(filename, inode);
        const handle = { inode };
        handle.writeFile = async text => {
            await this.step('writeFile');
            this.writeFileSync(handle, text);
        };
        handle.sync = async () => { await this.step('sync'); this.fsyncSync(handle); };
        handle.close = async () => { await this.step('close'); this.closeSync(handle); };
        this.handles.add(handle);
        return handle;
    }
    writeFileSync(handle, text) { this.fail('writeFileSync'); handle.inode.text = text; }
    fsyncSync() { this.fail('fsyncSync'); }
    closeSync(handle) { this.handles.delete(handle); }
    renameSync(from, to) {
        this.fail('renameSync');
        if (!this.paths.has(from)) throw Object.assign(new Error('missing path'), { code: 'ENOENT' });
        this.paths.set(to, this.paths.get(from));
        this.paths.delete(from);
    }
    unlinkSync(filename) {
        this.fail('unlinkSync');
        if (!this.paths.delete(filename)) throw Object.assign(new Error('missing path'), { code: 'ENOENT' });
    }
    rmdirSync(directory) {
        assert(![...this.paths.keys()].some(p => p.startsWith(directory + '/')));
        this.directories.delete(directory);
    }
    snapshot() { return JSON.parse(this.paths.get(FILE).text); }
    assertClean() {
        assert.deepEqual([...this.paths.keys()], [FILE]);
        assert.equal(this.directories.size, 0);
        assert.equal(this.handles.size, 0);
    }
}

function fixture() {
    const disk = new FileModel();
    const flow = store({ logfireReady: true, logsDirty: true, logs: { device: ['one'] } });
    const context = store();
    const errors = [], warnings = [];
    const node = { error: text => errors.push(text), warn: text => warnings.push(text) };
    const args = [disk, flow, context, node];
    initialize(...args);
    return { disk, flow, context, errors, warnings, args,
        save: () => save(...args), stop: () => stop(...args), init: () => initialize(...args) };
}

async function settle() {
    // All I/O is modeled with promises; drain their microtasks, without timers.
    for (let i = 0; i < 100; i++) await Promise.resolve();
}

const tests = [];
const test = (name, body) => tests.push({ name, body });

for (const pauseAt of ['mkdtemp', 'open', 'writeFile', 'sync', 'close']) {
    test('new log during stop; periodic save paused at ' + pauseAt, async () => {
        const f = fixture(), gate = f.disk.pause(pauseAt);
        f.save(); await settle();
        assert(gate.reached, 'save reached controlled pause');
        f.flow.get('logs').device.push('two'); f.flow.set('logsDirty', true);
        f.stop();
        assert.deepEqual(f.disk.snapshot(), { device: ['one', 'two'] });
        gate.release(); await settle();
        assert.deepEqual(f.disk.snapshot(), { device: ['one', 'two'] });
        assert.equal(f.flow.get('logsDirty'), false);
        assert.deepEqual(f.errors, []); assert.deepEqual(f.warnings, []);
        f.disk.assertClean();
    });
}
test('stop flushes in-flight snapshot when dirty is already false', async () => {
    const f = fixture(), gate = f.disk.pause('writeFile');
    f.save(); await settle(); assert(gate.reached);
    assert.equal(f.flow.get('logsDirty'), false);
    f.stop();
    // Must be saved before resuming old work: process exit can happen here.
    assert.deepEqual(f.disk.snapshot(), { device: ['one'] });
    gate.release(); await settle(); f.disk.assertClean();
});
test('redeploy cannot revive an old callback or overwrite the replacement save', async () => {
    const f = fixture(), gate = f.disk.pause('writeFile');
    f.save(); await settle(); assert(gate.reached);
    f.stop(); f.init();
    f.flow.get('logs').device.push('new deployment'); f.flow.set('logsDirty', true);
    f.save(); await settle();
    gate.release(); await settle();
    assert.deepEqual(f.disk.snapshot(), { device: ['one', 'new deployment'] });
    assert.equal(f.flow.get('logsDirty'), false); f.disk.assertClean();
});
test('concurrent ticks serialize saves and retain newly dirty data', async () => {
    const f = fixture(), gate = f.disk.pause('writeFile');
    f.save(); await settle(); assert(gate.reached);
    f.flow.get('logs').device.push('two'); f.flow.set('logsDirty', true);
    f.save(); await settle(); assert.equal(f.disk.sequence, 1);
    gate.release(); await settle();
    assert.equal(f.flow.get('logsDirty'), true);
    f.save(); await settle();
    assert.deepEqual(f.disk.snapshot(), { device: ['one', 'two'] }); f.disk.assertClean();
});
for (const operation of ['mkdtemp', 'open', 'writeFile', 'sync', 'renameSync']) {
    test('periodic ' + operation + ' failure restores dirty state and cleans up', async () => {
        const f = fixture(); f.disk.failure = operation;
        f.save(); await settle();
        assert.equal(f.flow.get('logsDirty'), true);
        assert.equal(f.errors.length, 1); f.disk.assertClean();
        assert.deepEqual(f.disk.snapshot(), { device: ['previous'] });
        f.save(); await settle();
        assert.deepEqual(f.disk.snapshot(), { device: ['one'] }); f.disk.assertClean();
    });
}
for (const operation of ['mkdtempSync', 'openSync', 'writeFileSync', 'fsyncSync', 'renameSync']) {
    test('final ' + operation + ' failure preserves snapshot and dirty state', async () => {
        const f = fixture(); f.disk.failure = operation;
        f.stop();
        assert.equal(f.flow.get('logsDirty'), true);
        assert.equal(f.errors.length, 1); f.disk.assertClean();
        assert.deepEqual(f.disk.snapshot(), { device: ['previous'] });
    });
}
test('failed final flush still prevents an older in-flight save from publishing', async () => {
    const f = fixture(), gate = f.disk.pause('writeFile');
    f.save(); await settle(); assert(gate.reached);
    f.flow.get('logs').device.push('two'); f.flow.set('logsDirty', true);
    f.disk.failure = 'renameSync'; f.stop();
    gate.release(); await settle();
    assert.equal(f.flow.get('logsDirty'), true);
    assert.deepEqual(f.disk.snapshot(), { device: ['previous'] }); f.disk.assertClean();
});
test('clean idle stop and unready store do not replace the saved snapshot', async () => {
    const f = fixture(); f.flow.set('logsDirty', false);
    f.save(); f.stop(); await settle();
    assert.deepEqual(f.disk.snapshot(), { device: ['previous'] });
    f.init(); f.flow.set('logsDirty', true); f.flow.set('logfireReady', false);
    f.save(); f.stop(); await settle();
    assert.deepEqual(f.disk.snapshot(), { device: ['previous'] }); f.disk.assertClean();
});

test('serialization failure is retryable and does not leave saving stuck', async () => {
    const f = fixture(); f.flow.get('logs').cycle = f.flow.get('logs');
    f.save(); await settle();
    assert.equal(f.flow.get('logsDirty'), true);
    assert.equal(f.errors.length, 1); f.disk.assertClean();
    delete f.flow.get('logs').cycle;
    f.save(); await settle();
    assert.deepEqual(f.disk.snapshot(), { device: ['one'] }); f.disk.assertClean();
});

// Complement the inode model with real filesystem I/O. Only the destination
// pathname is substituted; the write/flush/rename/finalize code is unchanged.
for (const newEntry of [false, true]) {
    test('real filesystem stop with ' + (newEntry ? 'new dirty data' : 'only in-flight data'), async () => {
        const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'logfire-persistence-'));
        const filename = path.join(temporary, 'logs.json');
        const load = name => new Function('fs', 'flow', 'context', 'node',
            fs.readFileSync(path.join(dir, name), 'utf8')
                .replaceAll(JSON.stringify(FILE), JSON.stringify(filename)));
        let release, reached = false;
        const gate = new Promise(resolve => { release = resolve; });
        const realFs = Object.create(fs);
        Object.defineProperty(realFs, 'promises', { value: {
            ...fs.promises,
            open: async (...args) => {
                const handle = await fs.promises.open(...args);
                return {
                    writeFile: async (...writeArgs) => {
                        reached = true; await gate; return handle.writeFile(...writeArgs);
                    },
                    sync: () => handle.sync(), close: () => handle.close()
                };
            }
        } });
        const f = fixture(); f.args[0] = realFs;
        async function until(condition) {
            const deadline = Date.now() + 5000;
            while (!condition()) {
                assert(Date.now() < deadline, 'filesystem operation timed out');
                await new Promise(resolve => setTimeout(resolve, 5));
            }
        }
        try {
            load('save_logs.js')(...f.args);
            await until(() => reached);
            if (newEntry) {
                f.flow.get('logs').device.push('two'); f.flow.set('logsDirty', true);
            }
            load('save_logs.finalize.js')(...f.args);
            const expected = newEntry ? { device: ['one', 'two'] } : { device: ['one'] };
            assert.deepEqual(JSON.parse(fs.readFileSync(filename, 'utf8')), expected);
            release();
            await until(() => !(f.context.get('logfireSaveState') || {}).saving && !f.context.get('saving'));
            assert.deepEqual(JSON.parse(fs.readFileSync(filename, 'utf8')), expected);
            assert.deepEqual(fs.readdirSync(temporary), ['logs.json']);
            assert.deepEqual(f.errors, []); assert.deepEqual(f.warnings, []);
        } finally {
            release();
            // This directory was created by this test and contains no user data.
            await new Promise(resolve => setTimeout(resolve, 20));
            fs.rmSync(temporary, { recursive: true, force: true });
        }
    });
}

(async () => {
    let failed = 0;
    for (const { name, body } of tests) {
        try { await body(); console.log('PASS ' + name); }
        catch (error) { failed++; console.error('FAIL ' + name + '\n' + error.stack); }
    }
    console.log(`${tests.length - failed}/${tests.length} persistence checks passed`);
    process.exitCode = failed ? 1 : 0;
})();
