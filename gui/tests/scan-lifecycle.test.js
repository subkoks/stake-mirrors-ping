const { test } = require('node:test');
const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const { createBridge } = require('../bridge');
function child() {
  const proc = new EventEmitter();
  proc.stdout = new EventEmitter(); proc.stderr = new EventEmitter();
  proc.kill = () => true;
  return proc;
}
test('stop owns child until close; restart cannot lose its process reference', async () => {
  const children = [];
  const bridge = createBridge(() => { const p = child(); children.push(p); return p; }, 'python', 'api.py');
  const first = bridge.request('run-scan', {}, true);
  const rejected = assert.rejects(first, /cancelled/);
  const stopped = bridge.stop();
  await assert.rejects(bridge.request('run-scan', {}, true), /already running/);
  children[0].emit('close', null);
  await rejected; await stopped;
  const second = bridge.request('run-scan', {}, true);
  const secondRejected = assert.rejects(second, /cancelled/);
  // Repeated stale callbacks cannot clear the current process.
  children[0].emit('close', null);
  const secondStop = bridge.stop();
  children[1].emit('close', null);
  await secondRejected; assert.equal((await secondStop).success, true);
});
test('structured errors and successful payloads cross the bridge', async () => {
  const proc = child(); const bridge = createBridge(() => proc, 'python', 'api.py');
  const pending = bridge.request('get-config');
  proc.stdout.emit('data', '{"success":true,"config":{"mirrors":[]}}');
  proc.emit('close', 0);
  assert.equal((await pending).success, true);
});
