const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

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
  mainWindow.webContents.on('new-window', (event) => event.preventDefault());

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

// Python bridge - spawn Python subprocess for scans
let pythonProcess = null;

// Resolve the Python interpreter that has the project dependencies installed.
// The project's deps (aiohttp, curl_cffi, pydantic, ...) live in .venv, not in
// the system `python3`. Prefer the venv; fall back to `python3`/`python` so the
// app still launches in dev environments where deps are installed globally.
function resolvePythonPath() {
  const candidates = [
    path.join(__dirname, '..', '.venv', 'bin', 'python'),
    path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe'), // Windows
    process.platform === 'win32' ? 'python' : 'python3',
  ];
  for (const candidate of candidates) {
    try {
      // spawnSync returns null/throws if the binary is missing
      const { error } = require('child_process').spawnSync(candidate, ['-c', 'pass'], {
        stdio: 'ignore',
      });
      if (!error) return candidate;
    } catch (e) {
      // try next candidate
    }
  }
  return process.platform === 'win32' ? 'python' : 'python3';
}

const PYTHON_PATH = resolvePythonPath();

ipcMain.handle('run-scan', async (event, config) => {
  return new Promise((resolve, reject) => {
    const pythonPath = PYTHON_PATH;
    const scriptPath = path.join(__dirname, '..', 'src', 'core', 'api.py');

    pythonProcess = spawn(pythonPath, [scriptPath, 'run-scan', JSON.stringify(config)]);

    let stdout = '';
    let stderr = '';

    pythonProcess.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    pythonProcess.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    pythonProcess.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse Python output: ${e.message}`));
        }
      } else {
        // The Python bridge prints its structured error JSON to stdout, not
        // stderr. Surface that message if present, else fall back to stderr.
        let detail = stderr.trim();
        try {
          const parsed = JSON.parse(stdout);
          if (parsed && parsed.error) detail = parsed.error;
        } catch (_) {
          /* stdout was not JSON */
        }
        reject(new Error(`Python process exited with code ${code}: ${detail}`));
      }
      pythonProcess = null;
    });

    pythonProcess.on('error', (err) => {
      reject(new Error(`Failed to spawn Python: ${err.message}`));
      pythonProcess = null;
    });
  });
});

ipcMain.handle('get-history-stats', async (event, options) => {
  return new Promise((resolve, reject) => {
    const pythonPath = PYTHON_PATH;
    const scriptPath = path.join(__dirname, '..', 'src', 'core', 'api.py');

    const proc = spawn(pythonPath, [scriptPath, 'get-history-stats', JSON.stringify(options || {})]);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse Python output: ${e.message}`));
        }
      } else {
        let detail = stderr.trim();
        try {
          const parsed = JSON.parse(stdout);
          if (parsed && parsed.error) detail = parsed.error;
        } catch (_) {
          /* stdout was not JSON */
        }
        reject(new Error(`Python process exited with code ${code}: ${detail}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn Python: ${err.message}`));
    });
  });
});

ipcMain.handle('get-config', async () => {
  return new Promise((resolve, reject) => {
    const pythonPath = PYTHON_PATH;
    const scriptPath = path.join(__dirname, '..', 'src', 'core', 'api.py');

    const proc = spawn(pythonPath, [scriptPath, 'get-config']);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse Python output: ${e.message}`));
        }
      } else {
        let detail = stderr.trim();
        try {
          const parsed = JSON.parse(stdout);
          if (parsed && parsed.error) detail = parsed.error;
        } catch (_) {
          /* stdout was not JSON */
        }
        reject(new Error(`Python process exited with code ${code}: ${detail}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn Python: ${err.message}`));
    });
  });
});

ipcMain.handle('update-config', async (event, config) => {
  return new Promise((resolve, reject) => {
    const pythonPath = PYTHON_PATH;
    const scriptPath = path.join(__dirname, '..', 'src', 'core', 'api.py');

    const proc = spawn(pythonPath, [scriptPath, 'update-config', JSON.stringify(config)]);

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (data) => {
      stdout += data.toString();
    });

    proc.stderr.on('data', (data) => {
      stderr += data.toString();
    });

    proc.on('close', (code) => {
      if (code === 0) {
        try {
          const result = JSON.parse(stdout);
          resolve(result);
        } catch (e) {
          reject(new Error(`Failed to parse Python output: ${e.message}`));
        }
      } else {
        let detail = stderr.trim();
        try {
          const parsed = JSON.parse(stdout);
          if (parsed && parsed.error) detail = parsed.error;
        } catch (_) {
          /* stdout was not JSON */
        }
        reject(new Error(`Python process exited with code ${code}: ${detail}`));
      }
    });

    proc.on('error', (err) => {
      reject(new Error(`Failed to spawn Python: ${err.message}`));
    });
  });
});

ipcMain.handle('stop-scan', async () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
    return { success: true };
  }
  return { success: false, message: 'No scan running' };
});
