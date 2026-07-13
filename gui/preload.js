const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  runScan: (config) => ipcRenderer.invoke('run-scan', config),
  getHistoryStats: (options) => ipcRenderer.invoke('get-history-stats', options),
  getConfig: () => ipcRenderer.invoke('get-config'),
  updateConfig: (config) => ipcRenderer.invoke('update-config', config),
  stopScan: () => ipcRenderer.invoke('stop-scan'),
  onScanProgress: (callback) => ipcRenderer.on('scan-progress', callback),
});
