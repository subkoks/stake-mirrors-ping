const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  onScanProgress: (callback) => {
    if (typeof callback !== 'function') throw new Error('Expected callback');
    const listener = (_event, progress) => callback(progress);
    ipcRenderer.on('scan-progress', listener);
    return () => ipcRenderer.removeListener('scan-progress', listener);
  },
  appInfo: () => ipcRenderer.invoke('app-info'),
  openSupport: () => ipcRenderer.invoke('open-support'),
  copyDiagnostics: () => ipcRenderer.invoke('copy-diagnostics'),
  checkUpdates: () => ipcRenderer.invoke('check-updates'),
  openRelease: () => ipcRenderer.invoke('open-release'),
  openMirror: (url) => ipcRenderer.invoke('open-mirror', { url }),
  runScan: (config) => ipcRenderer.invoke('run-scan', config),
  getHistoryStats: (options) => ipcRenderer.invoke('get-history-stats', options),
  getConfig: () => ipcRenderer.invoke('get-config'),
  updateConfig: (config) => ipcRenderer.invoke('update-config', config),
  stopScan: () => ipcRenderer.invoke('stop-scan'),
});
