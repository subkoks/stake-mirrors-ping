// Developer-only rendered Electron tests. No live scans or production user data.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const gui = path.resolve(__dirname, '..');
const python = process.env.STAKE_E2E_PYTHON || path.join(gui, '..', '.venv', 'bin', 'python');
const packaged = process.env.STAKE_E2E_EXECUTABLE || (process.argv.includes('--packaged') ? path.join(gui, 'dist', process.arch === 'arm64' ? 'mac-arm64' : 'mac', 'Stake Mirrors Ping.app', 'Contents/MacOS/Stake Mirrors Ping') : null);
const fixture = path.join(__dirname, 'fixture_bridge.py');
const base = fs.mkdtempSync(path.join(process.env.STAKE_E2E_OUTPUT || os.tmpdir(), 'stake94-e2e-'));
const wrapper = path.join(base, 'fixture-python');
fs.writeFileSync(wrapper, `#!${python}\nimport runpy,sys\nsys.argv=[${JSON.stringify(fixture)},*sys.argv[1:]]\nrunpy.run_path(${JSON.stringify(fixture)},run_name='__main__')\n`, { mode: 0o700 });
let passed = 0;
async function launch(name, interpreter, preference = false) {
  const data = path.join(base, name); fs.mkdirSync(data);
  const env = { ...process.env, STAKE_PYTHON: interpreter, PATH: '/usr/bin:/bin:/usr/sbin:/sbin' };
  delete env.VIRTUAL_ENV; delete env.CONDA_PREFIX;
  if (preference) {
    fs.writeFileSync(path.join(data, 'python-path.txt'), interpreter);
    delete env.STAKE_PYTHON;
  }
  // Never forward account tokens into a fixture process.
  delete env.STAKE_SESSION_TOKEN; delete env.STAKE_TRUSTED_DOMAINS;
  const app = await electron.launch({ ...(packaged ? { executablePath: packaged } : {}),
    args: [...(packaged ? [] : [gui]), `--user-data-dir=${data}`], env, cwd: base, timeout: 30000 });
  const page = await app.firstWindow();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  return { app, page, data, errors };
}
async function check(name, action) { await action(); passed++; console.log(`PASS ${name}`); }
async function waitFile(file) {
  const start = Date.now();
  while (!fs.existsSync(file)) {
    if (Date.now() - start > 10000) throw new Error('Fixture child did not start');
    await new Promise(r => setTimeout(r, 20));
  }
}
function exists(pid) { try { process.kill(pid, 0); return true; } catch { return false; } }
(async () => {
  let current;
  try {
    current = await launch('missing', path.join(base, 'missing-python'));
    await current.page.locator('#error-container').getByText('Python 3.12+', { exact: false }).waitFor();
    assert.equal(await current.page.locator('#run-scan-btn').isDisabled(), true);
    assert.match(await current.page.locator('#error-container').innerText(), /python-path.txt/);
    await current.app.close(); passed++; console.log('PASS missing Python renders actionable error');

    const empty = path.join(base, 'empty-python');
    execFileSync(python, ['-m', 'venv', '--without-pip', empty]);
    current = await launch('missing-dependencies', path.join(empty, 'bin', 'python'));
    await current.page.locator('#error-container').getByText('Python 3.12+', { exact: false }).waitFor();
    assert.equal(await current.page.locator('#run-scan-btn').isDisabled(), true);
    await current.app.close(); passed++; console.log('PASS clean Python without requirements renders prerequisite error');

    current = await launch('real-python', python, true);
    await current.page.waitForFunction(() => !document.getElementById('run-scan-btn').disabled);
    const canonical = fs.readFileSync(path.join(gui, '..', 'config.yaml'), 'utf8').match(/^  - domain:/gm).length;
    assert.match(await current.page.locator('#inventory-count').innerText(), new RegExp(`^${canonical} configured`));
    assert.equal(current.errors.length, 0, current.errors.join('\n'));
    assert.equal(await current.app.evaluate(({ app }) => app.isPackaged), Boolean(packaged));
    assert.equal(await current.app.evaluate(() => process.versions.electron), require('../package.json').devDependencies.electron);
    await current.app.close(); passed++; console.log('PASS real Python/config outside checkout without activated venv');

    current = await launch('offline-scans', wrapper);
    const { app, page, data, errors } = current;
    await page.waitForFunction(() => !document.getElementById('run-scan-btn').disabled);
    await check('settings preserve supported timeout range and IPC rejects arbitrary paths', async () => {
      await page.evaluate(() => window.electronAPI.updateConfig({ timeout_seconds: 90 }));
      await page.reload();
      await page.waitForFunction(() => !document.getElementById('run-scan-btn').disabled);
      assert.equal(await page.locator('#timeout').inputValue(), '90');
      await assert.rejects(page.evaluate(() => window.electronAPI.runScan({ config_path: '/tmp/unapproved.yaml' })), /Unsupported option/);
    });
    await check('start renders progress, results, honest states and missing-last ranking', async () => {
      await page.locator('#run-scan-btn').click();
      await page.locator('#scan-status').getByText('Scanning', { exact: true }).waitFor();
      await page.waitForFunction(() => document.querySelector('#scan-status').textContent.includes('Scan complete'));
      assert.equal(await page.locator('#mirrors-body tr').count(), canonical);
      await page.screenshot({ path: path.join(base, 'rendered-results.png'), animations: 'disabled' });
      assert.equal(await page.locator('#mirrors-body tr').first().locator('td').last().innerText(), '0.0ms');
      for (const text of ['dns error', 'blocked or challenged', 'rate limited']) assert.equal(await page.getByText(text, { exact: true }).isVisible(), true);
      assert.equal(await page.locator('#mirrors-body tr').last().locator('td').last().innerText(), '—');
    });
    await check('history loads from isolated fixture database', async () => {
      await page.getByRole('button', { name: 'History', exact: true }).click();
      await page.locator('#load-history-btn').click();
      await page.waitForFunction(() => document.querySelectorAll('#history-body tr').length > 1);
      assert.equal(await page.locator('#history-body tr').count(), canonical);
      await page.getByRole('button', { name: 'Mirrors', exact: true }).click();
    });
    await check('cancel and restart discard old scan results', async () => {
      fs.rmSync(path.join(data, 'scan.pid'), { force: true });
      fs.writeFileSync(path.join(data, 'scenario.txt'), 'slow');
      await page.locator('#run-scan-btn').click();
      await page.waitForFunction(() => !document.getElementById('stop-scan-btn').disabled);
      // Wait for the actual fixture child, not just renderer state.
      await waitFile(path.join(data, 'scan.pid'));
      await page.locator('#stop-scan-btn').click();
      await page.waitForFunction(() => !document.getElementById('run-scan-btn').disabled);
      fs.writeFileSync(path.join(data, 'scenario.txt'), 'restart');
      await page.locator('#run-scan-btn').click();
      await page.locator('#scan-status').getByText('Scan complete · restart', { exact: true }).waitFor();
    });
    await check('all failed scan clears dashboard latency values', async () => {
      fs.writeFileSync(path.join(data, 'scenario.txt'), 'failed');
      await page.locator('#run-scan-btn').click();
      await page.locator('#scan-status').getByText('Scan complete · failed', { exact: true }).waitFor();
      assert.equal(await page.locator('#stat-fastest').textContent(), '—');
      assert.equal(await page.locator('#stat-avg').textContent(), '—');
    });
    await check('unsafe new windows are denied and renderer has no Node access', async () => {
      assert.equal(await page.evaluate(() => typeof window.require), 'undefined');
      await page.evaluate(() => window.open('file:///etc/passwd'));
      assert.equal(app.windows().length, 1);
      const before = errors.length;
      await page.evaluate(() => window.open('javascript:alert(1)'));
      assert.equal(app.windows().length, 1);
      const blocked = errors.splice(before);
      assert.equal(blocked.length, 1);
      assert.match(blocked[0], /^Running the JavaScript URL violates the following Content Security Policy/);
      console.log('Expected security diagnostic: CSP blocked javascript URL');
    });
    await check('window shutdown terminates an active scan child', async () => {
      fs.rmSync(path.join(data, 'scan.pid'), { force: true });
      fs.writeFileSync(path.join(data, 'scenario.txt'), 'slow');
      await page.locator('#run-scan-btn').click();
      await waitFile(path.join(data, 'scan.pid'));
      const pid = Number(fs.readFileSync(path.join(data, 'scan.pid')));
      await page.close();
      const start = Date.now();
      while (exists(pid) && Date.now() - start < 7000) await new Promise(r => setTimeout(r, 30));
      assert.equal(exists(pid), false);
    });
    await check('macOS close and reactivate reloads a usable bridge', async () => {
      const windowPromise = app.waitForEvent('window');
      await app.evaluate(({ app }) => app.emit('activate'));
      const reopened = await windowPromise;
      await reopened.waitForFunction(() => !document.getElementById('run-scan-btn').disabled);
      fs.writeFileSync(path.join(data, 'scenario.txt'), 'reopened');
      await reopened.locator('#run-scan-btn').click();
      await reopened.locator('#scan-status').getByText('Scan complete · reopened', { exact: true }).waitFor();
      assert.match(await reopened.locator('#inventory-count').innerText(), new RegExp(`^${canonical} configured`));
    });
    assert.deepEqual(errors, []);
    await app.close();
    console.log(`${passed} rendered scenarios passed; diagnostics directory ${base}`);
  } catch (error) {
    console.error(error);
    console.error('Diagnostics:', base, current?.errors);
    if (current) { await current.page.screenshot({ path: path.join(base, 'failure.png') }).catch(() => {}); await current.app.close().catch(() => {}); }
    process.exitCode = 1;
  }
})();
