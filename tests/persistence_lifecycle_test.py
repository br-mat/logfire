"""Check real Node-RED stop/redeploy during a deliberately paused snapshot write.

Creates and removes its own disposable containers; never targets an existing hub.
Requires Docker or Podman and the selected Node-RED image.
"""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parent.parent
PAUSED = '/data/logfire-test-paused'
RELEASE = '/data/logfire-test-release'
DONE = '/data/logfire-test-done'


def wait_for(predicate, description, timeout=60):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.1)
    raise AssertionError('Timed out: ' + description)


def fixture_flow():
    source = ROOT / 'nodered' / 'functions'
    body = (source / 'save_logs.js').read_text(encoding='utf-8')
    write = 'await handle.writeFile(data, "utf8");'
    assert body.count(write) == 1
    # Only test instrumentation: hold the actual file handle before writing.
    # Native timers survive Function-node teardown so the old callback can be
    # released after redeploy. This hook is never written into the project flow.
    gate = '''
        fs.writeFileSync("/data/logfire-test-paused", "1");
        await new Promise((resolve, reject) => {
            var deadline = Date.now() + 60000;
            var timer = testTimers.setInterval(() => {
                if (fs.existsSync("/data/logfire-test-release")) {
                    testTimers.clearInterval(timer); resolve();
                } else if (Date.now() > deadline) {
                    testTimers.clearInterval(timer); reject(new Error("test gate timeout"));
                }
            }, 25);
        });
    '''
    body = body.replace(write, gate + write)
    assert body.count('state.saving = false;') == 1
    body = body.replace('state.saving = false;',
                        'state.saving = false; fs.writeFileSync("' + DONE + '", "1");')
    return [
        {'id': 'test-tab', 'type': 'tab', 'label': 'Disposable persistence lifecycle test'},
        {'id': 'set', 'z': 'test-tab', 'type': 'http in', 'url': '/set', 'method': 'post',
         'wires': [['update']]},
        {'id': 'update', 'z': 'test-tab', 'type': 'function', 'outputs': 2, 'libs': [],
         'func': 'var input = msg.payload; flow.set("logs", {device: input.entries});'
                 'flow.set("logfireReady", true); flow.set("logsDirty", true);'
                 'msg.payload = "OK"; return [msg, input.save ? {} : null];',
         'wires': [['response'], ['save']]},
        {'id': 'response', 'z': 'test-tab', 'type': 'http response', 'wires': []},
        {'id': 'save', 'z': 'test-tab', 'type': 'function', 'outputs': 0,
         'func': body, 'initialize': (source / 'save_logs.initialize.js').read_text(encoding='utf-8'),
         'finalize': (source / 'save_logs.finalize.js').read_text(encoding='utf-8'),
         'libs': [{'var': 'fs', 'module': 'fs'}, {'var': 'testTimers', 'module': 'timers'}],
         'wires': []},
    ]


def scenario(engine, image, mode, newly_dirty):
    name = 'logfire-persistence-test-' + uuid.uuid4().hex[:12]

    def run(*args, check=True):
        return subprocess.run([engine, *args], check=check, capture_output=True, text=True, timeout=90)

    try:
        run('run', '-d', '--name', name, '-p', '127.0.0.1::1880/tcp', image)
        address = run('port', name, '1880/tcp').stdout.strip().splitlines()[0]
        url = 'http://' + address

        def request(route, data=None):
            headers = {'Content-Type': 'application/json', 'Node-RED-Deployment-Type': 'full'}
            payload = None if data is None else json.dumps(data).encode()
            with urllib.request.urlopen(urllib.request.Request(url + route, data=payload, headers=headers),
                                        timeout=30) as response:
                return response.read()

        def available():
            try:
                request('/flows')
                return True
            except (OSError, urllib.error.URLError):
                return False

        def exists(filename):
            return run('exec', name, 'test', '-f', filename, check=False).returncode == 0

        def snapshot():
            with tempfile.TemporaryDirectory(prefix='logfire-snapshot-') as temporary:
                target = Path(temporary) / 'logs.json'
                run('cp', name + ':/data/logfire_logs.json', str(target))
                return json.loads(target.read_text(encoding='utf-8'))

        wait_for(available, 'Node-RED startup')
        flow = fixture_flow()
        request('/flows', flow)

        # Deployment can return before HTTP routes are registered. Probe only
        # before the scenario starts; probing after redeploy would change logs.
        def routes_ready():
            try:
                request('/set', {'entries': [], 'save': False})
                return True
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return False
                raise

        wait_for(routes_ready, 'test flow HTTP routes')
        request('/set', {'entries': ['one'], 'save': True})
        wait_for(lambda: exists(PAUSED), 'write paused with open handle')
        expected = ['one', 'two'] if newly_dirty else ['one']
        if newly_dirty:
            request('/set', {'entries': expected, 'save': False})
        if mode == 'stop':
            run('stop', '-t', '10', name)
            state = json.loads(run('inspect', name).stdout)[0]['State']
            assert state['ExitCode'] != 137 and not state.get('OOMKilled'), state
        else:
            request('/flows', flow)
        assert snapshot() == {'device': expected}, 'final snapshot missing before old write resumes'
        if mode == 'redeploy':
            run('exec', name, 'touch', RELEASE)
            wait_for(lambda: exists(DONE), 'old asynchronous save completed')
            assert snapshot() == {'device': expected}, 'old save overwrote final snapshot'
        print(f'PASS {mode}, newly_dirty={newly_dirty}', flush=True)
    except Exception:
        print(run('logs', name, check=False).stdout, flush=True)
        raise
    finally:
        # The generated name belongs exclusively to this test. Remove its
        # anonymous volume as well; never accept an existing container name.
        run('rm', '-f', '-v', name, check=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', choices=['docker', 'podman'], default='docker')
    parser.add_argument('--image', default='docker.io/nodered/node-red:5.0.10')
    args = parser.parse_args()
    for mode in ('stop', 'redeploy'):
        for newly_dirty in (False, True):
            scenario(args.engine, args.image, mode, newly_dirty)
    print('4/4 Node-RED lifecycle checks passed')


if __name__ == '__main__':
    main()
