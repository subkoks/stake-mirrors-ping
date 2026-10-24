const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { mirrorURL, releaseURL, newer, support } = require('../desktop-services');
const { resolveBackend, backendEnvironment } = require('../backend-runtime');
const { validatePayload } = require('../ipc-policy');
test('external links are fixed releases or configured HTTPS mirrors, never arbitrary schemes', () => {
  const config = { mirrors: [{ domain: 'stake.com', url: 'https://stake.com' }] };
  assert.equal(mirrorURL('https://stake.com', config), 'https://stake.com/');
  for (const url of ['file:///etc/passwd','javascript:alert(1)','https://stake.com@evil.com','https://localhost','https://127.0.0.1','https://stake.com:444','https://evil.com','https://stake.com/login']) assert.throws(() => mirrorURL(url, config));
  assert.throws(() => releaseURL('https://github.com/evil/releases'));
  assert.throws(() => validatePayload('open-mirror', { url: 'https://stake.com', extra: true }));
  assert.equal(newer('2.10.0','2.9.0'), true);
  assert.equal(newer('2.0.0','2.1.0'), false);
});
test('packaged backend ignores external interpreter settings and validates architecture, version and health', async () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'bundled-engine-'));
  try {
    fs.mkdirSync(path.join(root, 'backend'));
    fs.writeFileSync(path.join(root, 'backend/provenance.json'), JSON.stringify({ fixture: false, target: `${process.platform}-${process.arch}`, version: '2.1.0' }));
    let called;
    const run = async (file, args, options) => { called = { file, args, options }; return { stdout: JSON.stringify({ success: true, frozen: true, protocol: 1, architecture: process.arch, version: '2.1.0' }) }; };
    const result = await resolveBackend({ packaged: true, resourceRoot: root, dataRoot: root, version: '2.1.0', run });
    assert.equal(result.kind, 'bundled'); assert.match(called.file, /backend/); assert.deepEqual(called.args, ['health']);
    assert.equal(called.options.env.STAKE_PYTHON, undefined);
    await assert.rejects(resolveBackend({ packaged: true, resourceRoot: root, dataRoot: root, version: 'bad', run }), /reinstall/);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
test('support summary excludes secrets, paths, settings and scans; backend env rejects Python injection', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'support-'));
  try {
    const service = support(root, { version: '2.1.0', token: 'secret-test', path: root });
    service.record('TEST_FAILURE'); const text = service.summary();
    assert.ok(!text.includes('secret-test') && !text.includes(root));
    const env = backendEnvironment({ PATH: '/bin', STAKE_SESSION_TOKEN: 'secret-test', PYTHONPATH: root, DYLD_INSERT_LIBRARIES: 'bad' }, root);
    assert.equal(env.STAKE_SESSION_TOKEN, undefined); assert.equal(env.PYTHONPATH, undefined); assert.equal(env.DYLD_INSERT_LIBRARIES, undefined);
  } finally { fs.rmSync(root, { recursive: true, force: true }); }
});
const { EventEmitter } = require('node:events');
const { createBridge } = require('../bridge');
test('streaming bridge parses split UTF-8 lines, forwards progress and preserves the final API payload', async () => {
  const proc = new EventEmitter(); proc.stdout = new EventEmitter(); proc.stderr = new EventEmitter(); proc.kill = () => true;
  const events = []; let called;
  const bridge = createBridge((file,args) => { called = args; return proc; }, 'bundled-engine', null, {}, [], value => events.push(value));
  const pending = bridge.request('run-scan', {}, true);
  const message = Buffer.from(JSON.stringify({ type:'progress',stage:'Checking é',completed:1,total:2 })+'\n'+JSON.stringify({ type:'result',data:{success:true,mirrors:[]} })+'\n');
  for (let i=0;i<message.length;i+=3) proc.stdout.emit('data', message.subarray(i,i+3));
  proc.emit('close',0); assert.deepEqual(await pending,{success:true,mirrors:[]}); assert.equal(events[0].stage,'Checking é');
  assert.deepEqual(called,['run-scan','{}','--stream']);
});
test('invalid stream messages fail closed', async () => {
  const proc = new EventEmitter(); proc.stdout = new EventEmitter(); proc.stderr = new EventEmitter(); proc.kill = () => true;
  const bridge = createBridge(() => proc, 'engine', null, {}, []);
  const pending = bridge.request('run-scan', {}, true); const rejected = assert.rejects(pending,/Invalid/);
  proc.stdout.emit('data', Buffer.from('{"type":"progress","stage":"bad","completed":9,"total":2}\n'));
  proc.emit('close',0); await rejected;
});
test('mirror DNS validation rejects private, metadata and mixed public/private answers', async () => {
  const { checkedMirrorURL, publicAddress } = require('../desktop-services');
  const config = { mirrors: [{ domain:'stake.com', url:'https://stake.com' }] };
  for (const address of ['127.0.0.1','169.254.169.254','100.100.100.200','10.0.0.1','192.168.1.1','::1','fc00::1','fe80::1','::ffff:127.0.0.1']) assert.equal(publicAddress(address), false, address);
  await assert.rejects(checkedMirrorURL('https://stake.com', config, async () => [{ address:'8.8.8.8' },{ address:'127.0.0.1' }]), /public/);
  assert.equal(await checkedMirrorURL('https://stake.com', config, async () => [{ address:'8.8.8.8' }]), 'https://stake.com/');
});
