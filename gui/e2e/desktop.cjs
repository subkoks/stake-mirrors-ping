// Run against an actual packaged/installed executable. Production and fixture builds are separate.
const { _electron: electron } = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const { execFileSync } = require('node:child_process');
const fixture = process.argv.includes('--fixture');
const executable = process.env.STAKE_DESKTOP_EXECUTABLE;
if (!executable || !path.isAbsolute(executable)) throw new Error('Set STAKE_DESKTOP_EXECUTABLE to the installed application');
const base = fs.mkdtempSync(path.join(process.env.STAKE_E2E_OUTPUT || os.tmpdir(), 'stake-desktop-é-'));
const data = path.join(base, 'Saved data Å'); fs.mkdirSync(data);
fs.writeFileSync(path.join(data, 'python-path.txt'), path.join(base, 'nonexistent-python'));
let app; let page; let passed = 0; const errors = [];
const env = { ...process.env, STAKE_PYTHON: path.join(base, 'nonexistent-python'), PYTHONPATH: base };
for (const key of ['VIRTUAL_ENV', 'CONDA_PREFIX', 'STAKE_SESSION_TOKEN', 'STAKE_TRUSTED_DOMAINS']) delete env[key];
function gone(pid) { try { process.kill(pid, 0); return false; } catch { return true; } }
async function check(name, action) { await action(); console.log('PASS ' + name); passed++; }
async function launch(ready = true) {
  const started = Date.now();
  app = await electron.launch({ executablePath: executable, args: [`--user-data-dir=${data}`, ...(process.platform === 'linux' && process.env.STAKE_E2E_SANDBOX !== '1' ? ['--no-sandbox'] : [])], env, cwd: base, timeout: 45000 });
  page = await app.firstWindow(); page.on('pageerror', error => errors.push(error.message));
  if (ready) await page.locator('#run-scan-btn:enabled').waitFor({ timeout: 30000 });
  console.log(`READY_MS ${Date.now() - started}`);
}
async function scenario(mode) { fs.writeFileSync(path.join(data, 'scenario.txt'), mode); if (mode === 'partial') fs.rmSync(path.join(data, 'continue-scan'), { force:true }); }
async function scan(mode) {
  await scenario(mode); await page.locator('#run-scan-btn').click();
  if (mode === 'partial') { await page.locator('#scan-status').filter({ hasText:'of' }).waitFor(); fs.writeFileSync(path.join(data,'continue-scan'), 'continue'); }
  await page.locator('#scan-status').filter({ hasText: 'Scan complete' }).waitFor({ timeout: 20000 });
}
(async () => {
 try {
  await launch();
  await check('packaged launch uses bundled backend despite invalid external Python preferences', async () => {
    const info = await page.evaluate(() => window.electronAPI.appInfo());
    assert.equal(info.backend, 'bundled'); assert.equal(info.version, '2.1.0');
    assert.match(await page.locator('#inventory-count').innerText(), /mirrors ready/);
    assert.equal(await app.evaluate(() => process.versions.electron), require('../package.json').devDependencies.electron);
    const health = await app.evaluate(({ app }) => {
      const path = process.getBuiltinModule('path'); const fs = process.getBuiltinModule('fs'); const cp = process.getBuiltinModule('child_process');
      const resource = process.resourcesPath;
      const manifest = JSON.parse(fs.readFileSync(path.join(resource, 'backend/provenance.json')));
      const result = JSON.parse(cp.execFileSync(path.join(resource, 'backend', process.platform === 'win32' ? 'stake-backend.exe' : 'stake-backend'), ['health'], { encoding: 'utf8', windowsHide: true }));
      return { manifest, result, packaged: app.isPackaged };
    });
    assert.ok(health.packaged && health.result.frozen); assert.equal(health.result.python, '3.13.16'); assert.equal(health.manifest.fixture, fixture);
    assert.equal(health.result.architecture, process.arch); assert.match(health.result.native_tls, /curl/i);
  });
  await check('settings persist across application restart with existing user data', async () => {
    await page.locator('[data-panel="settings"]').click();
    await page.locator('#timeout').fill('17'); await page.locator('#save-settings-btn').click();
    await page.locator('#save-settings-btn').filter({ hasText: 'Saved' }).waitFor();
    await app.close();
    if (!fixture && process.platform === 'win32' && process.env.STAKE_DESKTOP_INSTALLER) {
      execFileSync(process.env.STAKE_DESKTOP_INSTALLER, ['/S', '/D='+path.dirname(executable)], { timeout:180000, windowsHide:true });
      console.log('PASS Windows reinstall over existing app preserves separate user data');
    }
    await launch();
    assert.equal(await page.locator('#timeout').inputValue(), '17');
    assert.ok(fs.existsSync(path.join(data, 'python-path.txt')));
  });
  await check('help and redacted diagnostics are GUI accessible; unsafe external links are rejected', async () => {
    await page.locator('[data-panel="help"]').click(); assert.match(await page.locator('#app-version').innerText(), /2.1.0/);
    await page.locator('#copy-diagnostics-btn').click(); await page.locator('#support-status').filter({ hasText: 'copied' }).waitFor();
    const summary = await app.evaluate(({ clipboard }) => clipboard.readText());
    assert.ok(!summary.includes(base) && !summary.includes('nonexistent-python'));
    for (const url of ['javascript:alert(1)', 'file:///etc/passwd', 'https://127.0.0.1']) {
      assert.equal(await page.evaluate(url => window.electronAPI.openMirror(url).then(() => false, () => true), url), true);
    }
  });
  await check('manual update check gives a trusted download action and recovers from failure', async () => {
    await app.evaluate(() => {
      const https = process.getBuiltinModule('https');
      const { EventEmitter } = process.getBuiltinModule('events');
      https.get = (_url, _options, callback) => {
        const request = new EventEmitter(); request.destroy = error => request.emit('error', error);
        queueMicrotask(() => { const response = new EventEmitter(); response.statusCode = 200; callback(response);
          response.emit('data', Buffer.from(JSON.stringify({ tag_name:'v99.0.0', html_url:'https://github.com/subkoks/stake-mirrors-ping/releases/tag/v99.0.0', draft:false, prerelease:false }))); response.emit('end'); });
        return request;
      };
    });
    await page.locator('#check-updates-btn').click(); await page.locator('#update-status').filter({ hasText:'99.0.0 is available' }).waitFor();
    await app.evaluate(() => { process.getBuiltinModule('https').get = () => { throw new Error('Offline fixture'); }; });
    await page.locator('#check-updates-btn').click(); await page.locator('#update-status').filter({ hasText:'Could not check' }).waitFor();
    assert.equal(await page.locator('#check-updates-btn').isEnabled(), true);
  });
  if (fixture) {
    await page.locator('[data-panel="mirrors"]').click();
    await check('measured progress, sorted partial results, blocked and rate-limit states', async () => {
      await scenario('partial'); await page.locator('#run-scan-btn').click();
      await page.locator('#scan-status').filter({ hasText: 'of' }).waitFor();
      fs.writeFileSync(path.join(data,'continue-scan'), 'continue');
      await page.locator('#scan-status').filter({ hasText: 'Scan complete' }).waitFor();
      const rows = page.locator('#mirrors-body tr'); assert.ok(await rows.count() > 10);
      assert.match(await page.locator('#mirrors-body').innerText(), /Blocked \/ challenge/);
      assert.match(await page.locator('#mirrors-body').innerText(), /Too many requests/);
      const values = await page.locator('#mirrors-body tr td:nth-child(6)').allTextContents();
      const numeric = values.filter(v => v.includes('ms')).map(parseFloat); assert.deepEqual(numeric, [...numeric].sort((a,b) => a-b));
      await page.screenshot({ path: path.join(base, 'desktop-results.png'), animations: 'disabled' });
    });
    await check('open mirror validates its configured destination before handing it to the browser', async () => {
      await app.evaluate(({ shell }) => {
        shell.openExternal = async url => { globalThis.testOpenedURL = url; };
        process.getBuiltinModule('dns').promises.lookup = async () => [{ address: '8.8.8.8', family: 4 }];
      });
      await page.locator('#mirrors-body button').first().click();
      await page.locator('#mirrors-body button').first().filter({ hasText: 'Opened' }).waitFor();
      const url = await app.evaluate(() => globalThis.testOpenedURL);
      assert.match(url, /^https:\/\//);
    });
    await check('history is saved and available from the GUI', async () => {
      await page.locator('[data-panel="history"]').click(); await page.locator('#load-history-btn').click();
      await page.locator('#history-body tr').filter({ hasText: 'stake' }).first().waitFor();
      const count = await page.locator('#history-body tr').count();
      await app.close(); await launch();
      await page.locator('[data-panel="history"]').click(); await page.locator('#load-history-btn').click();
      await page.locator('#history-body tr').filter({ hasText: 'stake' }).first().waitFor();
      assert.equal(await page.locator('#history-body tr').count(), count);
      await page.locator('[data-panel="mirrors"]').click();
    });
    await check('cancel and restart cannot mix results; child process exits', async () => {
      await scenario('slow'); await page.locator('#run-scan-btn').click();
      await page.locator('#scan-status').filter({ hasText: 'of' }).waitFor();
      const pid = Number(fs.readFileSync(path.join(data, 'scan.pid')));
      await page.locator('#stop-scan-btn').click(); await page.locator('#run-scan-btn:enabled').waitFor();
      assert.ok(gone(pid)); await scan('partial');
    });
    await check('no internet, empty results and backend failures offer recovery', async () => {
      await scan('offline'); assert.match(await page.locator('#scan-summary').innerText(), /Check your internet/);
      await scan('empty'); assert.match(await page.locator('#scan-summary').innerText(), /No results/);
      await scenario('failure'); await page.locator('#run-scan-btn').click();
      await page.locator('#scan-status').filter({ hasText: 'Scan failed' }).waitFor();
      await scan('partial');
    });
    await check('keyboard focus and 150 percent scaling remain usable', async () => {
      await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1.5));
      await page.locator('#run-scan-btn').focus(); assert.equal(await page.locator('#run-scan-btn').evaluate(node => node === document.activeElement), true);
      await page.keyboard.press('Tab'); assert.equal(await page.locator('#stop-scan-btn').isDisabled(), true);
      await app.evaluate(({ BrowserWindow }) => BrowserWindow.getAllWindows()[0].webContents.setZoomFactor(1));
    });
    await check('app shutdown terminates the active scan', async () => {
      await scenario('slow'); await page.locator('#run-scan-btn').click(); await page.locator('#scan-status').filter({ hasText: 'of' }).waitFor();
      const pid = Number(fs.readFileSync(path.join(data, 'scan.pid'))); await app.close(); app = null; assert.ok(gone(pid));
    });
  }
  if (!fixture) {
    const resource = await app.evaluate(() => process.resourcesPath);
    const engine = path.join(resource,'backend',process.platform === 'win32' ? 'stake-backend.exe' : 'stake-backend');
    let writable = true; try { fs.accessSync(engine, fs.constants.W_OK); } catch { writable = false; }
    if (writable) await check('missing bundled engine gives actionable error and retry recovers without touching user data', async () => {
      await app.close(); app = null; fs.renameSync(engine,engine+'.unavailable');
      try {
        await launch(false); await page.locator('#error-container').filter({ hasText:'reinstall' }).waitFor({ timeout:30000 });
        assert.equal(await page.locator('#run-scan-btn').isDisabled(),true);
        fs.renameSync(engine+'.unavailable',engine);
        await page.locator('#retry-startup-btn').click(); await page.locator('#run-scan-btn:enabled').waitFor({timeout:30000});
        assert.equal(await page.locator('#timeout').inputValue(),'17');
      } finally { if (fs.existsSync(engine+'.unavailable')) fs.renameSync(engine+'.unavailable',engine); }
    });
    else console.log('NOT_RUN engine mutation: installed files are read-only for the clean-environment user; covered by the writable disposable installation checks.');
  }
  assert.deepEqual(errors, []);
  console.log(`${passed} packaged desktop scenarios passed; diagnostics ${base}`);
 } catch (error) {
  if (page) await page.screenshot({ path: path.join(base, 'failure.png') }).catch(() => {});
  console.error(error); process.exitCode = 1;
 } finally { if (app) await app.close().catch(() => {}); }
})();
