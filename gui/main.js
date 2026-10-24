const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('node:path');
const fs = require('node:fs');
const { spawn } = require('node:child_process');
const { createBridge } = require('./bridge');
const { validateSender, validatePayload } = require('./ipc-policy');
const { resolvePython } = require('./python-runtime');

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

async function getBridge() {
  if (bridge) return bridge;
  if (!bridgePromise) {
    const generation = bridgeGeneration;
    bridgePromise = (async () => {
    const dataRoot = app.isPackaged || requestedData ? app.getPath('userData') : resourceRoot;
    fs.mkdirSync(dataRoot, { recursive: true });
    const config = path.join(dataRoot, 'config.yaml');
    if (!fs.existsSync(config)) fs.copyFileSync(path.join(resourceRoot, 'config.yaml'), config, fs.constants.COPYFILE_EXCL);
    const python = await resolvePython({ packaged: app.isPackaged, resourceRoot, dataRoot });
    if (quitting || generation !== bridgeGeneration) throw new Error("Application window is closed");
    bridge = createBridge(spawn, python, path.join(resourceRoot, 'src', 'core', 'api.py'), {
      cwd: dataRoot, shell: false, windowsHide: true,
      env: { ...process.env, STAKE_DATA_DIR: dataRoot, PYTHONNOUSERSITE: '1' },
    });
    return bridge;
    })().catch(error => { if (generation === bridgeGeneration) bridgePromise = null; throw error; });
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
app.on('before-quit', event => {
  if ((!bridge && !bridgePromise) || quitting) return;
  event.preventDefault();
  quitting = true;
  Promise.resolve(bridgePromise).then(service => service?.shutdown()).catch(() => {}).finally(() => app.quit());
});
