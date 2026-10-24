const { test } = require('node:test');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const { validateSender, validatePayload } = require('../ipc-policy');
const { resolvePython } = require('../python-runtime');
const { createBridge } = require('../bridge');
const { EventEmitter } = require('node:events');
const path = require('node:path');

test('IPC rejects subframes, foreign windows and non-app URLs', () => {
  const index = path.resolve('index.html');
  const frame = { url: pathToFileURL(index).href };
  const contents = { mainFrame: frame };
  const event = { sender: contents, senderFrame: frame };
  validateSender(event, { webContents: contents }, index);
  for (const invalid of [{ ...event, sender: {} }, { ...event, senderFrame: { ...frame } }, { ...event, senderFrame: { url: 'https://evil.example/' } }]) {
    assert.throws(() => validateSender(invalid, { webContents: contents }, index), /denied/);
  }
});
test('renderer cannot select executable, config path, token or unbounded scan settings', () => {
  for (const payload of [{ config_path: '/etc/passwd' }, { session_token: 'fake' }, { rounds: 0 }, { timeout: Infinity }, { rounds: 1.5 }, { skip_vpn: 'yes' }]) {
    assert.throws(() => validatePayload('run-scan', payload));
  }
  assert.deepEqual(validatePayload('run-scan', { rounds: 2, timeout: 1, skip_vpn: true }), { rounds: 2, timeout: 1, skip_vpn: true });
});
test('configured Python is checked without shell or development venv fallback', async () => {
  const checked = [];
  const python = path.resolve('controlled-python');
  assert.equal(await resolvePython({ packaged: true, resourceRoot: '/resources', dataRoot: '/unused', env: { STAKE_PYTHON: python }, run: async (...args) => { checked.push(args); } }), python);
  assert.equal(checked[0][1][0], '-I');
  assert.match(checked[0][1][2], /version_info < \(3,12\)/);
  await assert.rejects(resolvePython({ packaged: true, resourceRoot: '/resources', dataRoot: '/unused', env: { STAKE_PYTHON: python }, run: async () => { throw new Error('old or missing dependencies'); } }), /requirements.txt/);
});
test('shutdown terminates history/config children as well as the active scan', async () => {
  const children = [];
  function spawn() {
    const p = new EventEmitter(); p.stdout = new EventEmitter(); p.stderr = new EventEmitter();
    p.kill = () => { queueMicrotask(() => p.emit('close', null)); return true; };
    children.push(p); return p;
  }
  const bridge = createBridge(spawn, 'python', 'api.py');
  const scan = assert.rejects(bridge.request('run-scan', {}, true), /cancelled/);
  const history = assert.rejects(bridge.request('get-history-stats'), /cancelled/);
  await bridge.shutdown(); await scan; await history;
  assert.equal(children.length, 2);
  await assert.rejects(bridge.request('get-config'), /shutting down/);
});

test('Python dependency minimums match the public requirements manifest', () => {
  const fs = require('node:fs');
  const { MINIMUMS } = require('../python-runtime');
  const lines = fs.readFileSync(path.join(__dirname, '../../requirements.txt'), 'utf8').trim().split('\n');
  assert.deepEqual(Object.fromEntries(lines.map(line => line.trim().split('>='))), MINIMUMS);
});

test('installed packages contain no prereleases; all locked URLs use the public registry', () => {
  const fs = require('node:fs');
  const root = path.join(__dirname, '..');
  const lock = JSON.parse(fs.readFileSync(path.join(root, 'package-lock.json')));
  for (const [location, entry] of Object.entries(lock.packages)) {
    if (entry.resolved) assert.equal(new URL(entry.resolved).hostname, 'registry.npmjs.org');
    const file = path.join(root, location, 'package.json');
    if (location && fs.existsSync(file)) assert.doesNotMatch(JSON.parse(fs.readFileSync(file)).version, /-/);
  }
});
