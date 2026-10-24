// A scan owns its child until exit, including while cancellation is pending.
function createBridge(spawn, pythonPath, scriptPath, options = {}) {
  let active = null;
  function request(command, config, scan = false) {
    if (scan && active) return Promise.reject(new Error('A scan is already running'));
    return new Promise((resolve, reject) => {
      const proc = spawn(pythonPath, [scriptPath, command, JSON.stringify(config || {})], options);
      if (scan) active = proc;
      let stdout = '';
      let stderr = '';
      proc.stdout.on('data', data => { stdout += data.toString(); });
      proc.stderr.on('data', data => { stderr += data.toString(); });
      proc.on('error', err => {
        if (active === proc) active = null;
        reject(new Error(`Python could not start: ${err.message}`));
      });
      proc.on('close', code => {
        if (active === proc) active = null;
        try {
          const result = JSON.parse(stdout);
          if (code !== 0 || result.success === false) throw new Error(result.error || 'Python request failed');
          resolve(result);
        } catch (err) {
          reject(new Error(proc.cancelled ? 'Scan cancelled' : `Python request failed: ${err.message}${stderr ? ' (see Python runtime configuration)' : ''}`));
        }
      });
    });
  }
  async function stop() {
    const proc = active;
    if (!proc) return { success: false, message: 'No scan running' };
    proc.cancelled = true;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { proc.kill('SIGKILL'); }, 3000);
      const finish = () => { clearTimeout(timer); resolve({ success: true }); };
      proc.once('close', finish);
      if (!proc.kill()) {
        clearTimeout(timer);
        proc.removeListener('close', finish);
        reject(new Error('Could not stop scan'));
      }
    });
  }
  return { request, stop };
}
module.exports = { createBridge };
