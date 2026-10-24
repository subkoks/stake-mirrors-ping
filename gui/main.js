const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const { createBridge } = require('./bridge');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
      preload: path.join(__dirname, 'preload.js'),
    },
  });

  // Block any navigation away from the bundled app (defense against injected
  // links / redirects to external origins).
  mainWindow.webContents.on('will-navigate', (event, url) => {
    if (url !== mainWindow.webContents.getURL()) {
      event.preventDefault();
    }
  });
  mainWindow.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));

  mainWindow.loadFile('index.html');

  if (process.argv.includes('--dev')) {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Packaged applications require a Python interpreter with requirements installed.
const resourceRoot = app.isPackaged ? process.resourcesPath : path.join(__dirname, '..');
function resolvePythonPath() {
  const candidates = [
    path.join(resourceRoot, '.venv', 'bin', 'python'),
    path.join(resourceRoot, '.venv', 'Scripts', 'python.exe'),
    process.platform === 'win32' ? 'python' : 'python3',
  ];
  for (const candidate of candidates) {
    const result = require('child_process').spawnSync(candidate,
      ['-c', 'import sys; assert sys.version_info >= (3, 12); import aiohttp, certifi, curl_cffi, dotenv, pydantic, yaml, rich'],
      { stdio: 'ignore', timeout: 10000 });
    if (!result.error && result.status === 0) return candidate;
  }
  return candidates[candidates.length - 1];
}
let bridge;
function getBridge() {
  if (bridge) return bridge;
  const dataRoot = app.isPackaged ? app.getPath('userData') : resourceRoot;
  if (app.isPackaged) {
    fs.mkdirSync(dataRoot, { recursive: true });
    const config = path.join(dataRoot, 'config.yaml');
    if (!fs.existsSync(config)) fs.copyFileSync(path.join(resourceRoot, 'config.yaml'), config);
  }
  bridge = createBridge(spawn, resolvePythonPath(), path.join(resourceRoot, 'src', 'core', 'api.py'), {
    cwd: dataRoot,
    env: { ...process.env, STAKE_DATA_DIR: dataRoot },
  });
  return bridge;
}
ipcMain.handle('run-scan', (event, config) => getBridge().request('run-scan', config, true));
ipcMain.handle('get-history-stats', (event, options) => getBridge().request('get-history-stats', options));
ipcMain.handle('get-config', () => getBridge().request('get-config'));
ipcMain.handle('update-config', (event, config) => getBridge().request('update-config', config));
ipcMain.handle('stop-scan', () => getBridge().stop());
app.on('before-quit', () => { if (bridge) bridge.stop().catch(() => {}); });
