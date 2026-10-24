const { pathToFileURL } = require('node:url');

function validateSender(event, window, indexPath) {
  if (!window || event.sender !== window.webContents ||
      event.senderFrame !== window.webContents.mainFrame ||
      event.senderFrame.url !== pathToFileURL(indexPath).href) {
    throw new Error('IPC request denied: unexpected sender');
  }
}
function object(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Expected an options object');
  return value;
}
function validatePayload(command, value = {}) {
  const input = object(value);
  const allowed = command === 'run-scan'
    ? ['rounds', 'timeout', 'skip_geoip', 'skip_vpn', 'api_tests', 'save_history']
    : command === 'update-config' ? ['ping_rounds', 'timeout_seconds', 'concurrent_limit']
    : command === 'get-history-stats' ? ['hours'] : [];
  for (const [key, item] of Object.entries(input)) {
    if (!allowed.includes(key)) throw new Error(`Unsupported option: ${key}`);
    if (['skip_geoip', 'skip_vpn', 'api_tests', 'save_history'].includes(key)) {
      if (typeof item !== 'boolean') throw new Error(`${key} must be boolean`);
    } else {
      const maximum = key === 'hours' ? 8760 : key === 'concurrent_limit' ? 64 : key.includes('round') ? 20 : 120;
      if (typeof item !== 'number' || !Number.isFinite(item) || item <= 0 || item > maximum ||
          (key !== 'timeout' && key !== 'timeout_seconds' && !Number.isInteger(item))) {
        throw new Error(`Invalid ${key}`);
      }
    }
  }
  return input;
}
module.exports = { validateSender, validatePayload };
