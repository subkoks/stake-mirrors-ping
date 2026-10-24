const { app, BrowserWindow, ipcMain, shell, clipboard } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { createBridge } = require('./bridge');
const { validateSender, validatePayload } = require('./ipc-policy');
const { resolveBackend, backendEnvironment } = require('./backend-runtime');
const { mirrorURL, releaseURL, latestRelease, newer, support, RELEASE } = require('./desktop-services');

const requestedData = app.commandLine.getSwitchValue('user-data-dir');
if (requestedData) {
  if (!path.isAbsolute(requestedData)) throw new Error('--user-data-dir requires an absolute directory');
  app.setPath('userData', requestedData);
}
const indexPath = path.join(__dirname, 'index.html');
const resourceRoot = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
let mainWindow;
let bridge;
let bridgePromise;
let bridgeGeneration = 0;
let quitting = false;
let supportService;
const appInfo = { version: app.getVersion() };
function diagnostics() {
  if (!supportService) supportService = support(app.getPath('userData'), appInfo);
  return supportService;
}

async function getBridge() {
  if (bridge) return bridge;
  if (!bridgePromise) {
    const generation = bridgeGeneration;
    bridgePromise = (async () => {
    const dataRoot = app.isPackaged || requestedData ? app.getPath('userData') : resourceRoot;
    fs.mkdirSync(dataRoot, { recursive: true });
    const config = path.join(dataRoot, 'config.yaml');
    if (!fs.existsSync(config)) fs.copyFileSync(path.join(resourceRoot, 'config.yaml'), config, fs.constants.COPYFILE_EXCL);
    const backend = await resolveBackend({ packaged: app.isPackaged, resourceRoot, dataRoot, version: app.getVersion(), testBuild: require("./package.json").desktopTest === true });
    appInfo.backend = backend.kind;
    diagnostics().record('BACKEND_READY');
    if (quitting || generation !== bridgeGeneration) throw new Error("Application window is closed");
    bridge = createBridge(spawn, backend.executable, null, {
      cwd: dataRoot, shell: false, windowsHide: true,
      env: backendEnvironment(process.env, dataRoot),
    }, backend.args, progress => {
      if (generation === bridgeGeneration && mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('scan-progress', progress);
    });
    return bridge;
    })().catch(error => { if (generation === bridgeGeneration) bridgePromise = null; diagnostics().record('BACKEND_START_FAILED'); throw error; });
  }
  return bridgePromise;
}
function createWindow() {
  mainWindow = new BrowserWindow({ width: 1200, height: 800,
    webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true,
      webviewTag: false, preload: path.join(__dirname, 'preload.js') },
  });
  const contents = mainWindow.webContents;
  contents.on('will-navigate', event => event.preventDefault());
  contents.on('will-attach-webview', event => event.preventDefault());
  contents.setWindowOpenHandler(() => ({ action: 'deny' }));
  contents.session.setPermissionRequestHandler((_webContents, _permission, callback) => callback(false));
  contents.session.setPermissionCheckHandler(() => false);
  mainWindow.loadFile(indexPath);
  if (process.argv.includes('--dev')) contents.openDevTools();
  mainWindow.on('closed', () => {
    mainWindow = null;
    const previous = bridge;
    bridgeGeneration++;
    bridge = null;
    bridgePromise = null;
    if (previous) previous.shutdown().catch(() => {});
  });
}
app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
for (const command of ['run-scan', 'get-history-stats', 'get-config', 'update-config', 'stop-scan']) {
  ipcMain.handle(command, async (event, payload) => {
    validateSender(event, mainWindow, indexPath);
    const options = validatePayload(command, payload);
    const service = await getBridge();
    if (quitting || !mainWindow || mainWindow.isDestroyed()) throw new Error("Application window is closed");
    validateSender(event, mainWindow, indexPath);
    return command === 'stop-scan' ? service.stop() : service.request(command, options, command === 'run-scan');
  });
}

for (const command of ['app-info', 'open-support', 'copy-diagnostics', 'check-updates', 'open-release', 'open-mirror']) {
  ipcMain.handle(command, async (event, payload = {}) => {
    validateSender(event, mainWindow, indexPath);
    validatePayload(command, payload);
    if (command === 'app-info') return { version: app.getVersion(), platform: process.platform, architecture: process.arch, backend: appInfo.backend || 'not ready' };
    if (command === 'copy-diagnostics') { await clipboard.writeText(diagnostics().summary()); return { success: true }; }
    if (command === 'open-support') {
      const error = await shell.openPath(diagnostics().folder);
      if (error) throw new Error('The support folder could not be opened. Please try again.');
      return { success: true };
    }
    if (command === 'check-updates') {
      try { const result = await latestRelease(); return { ...result, available: newer(result.version, app.getVersion()) }; }
      catch (_) { diagnostics().record('UPDATE_CHECK_FAILED'); throw new Error('Could not check for updates. Check your internet connection and try again.'); }
    }
    if (command === 'open-release') { await shell.openExternal(releaseURL(RELEASE)); return { success: true }; }
    if (command === 'open-mirror') {
      const service = await getBridge();
      const config = await service.request('get-config');
      validateSender(event, mainWindow, indexPath);
      await shell.openExternal(mirrorURL(payload.url, config.config));
      return { success: true };
    }
  });
}

app.on('before-quit', event => {
  if ((!bridge && !bridgePromise) || quitting) return;
  event.preventDefault();
  quitting = true;
  Promise.resolve(bridgePromise).then(service => service?.shutdown()).catch(() => {}).finally(() => app.quit());
});
