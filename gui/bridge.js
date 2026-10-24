function createBridge(spawn, pythonPath, scriptPath, options = {}) {
  let active = null;
  let closing = false;
  const children = new Set();
  function request(command, config, scan = false) {
    if (closing) return Promise.reject(new Error('Application is shutting down'));
    if (scan && active) return Promise.reject(new Error('A scan is already running'));
    return new Promise((resolve, reject) => {
      const proc = spawn(pythonPath, ['-I', scriptPath, command, JSON.stringify(config || {})], options);
      children.add(proc);
      if (scan) active = proc;
      let stdout = '';
      let stderrBytes = 0;
      let overflow = false;
      proc.stdout.on('data', data => {
        if (stdout.length + data.length > 4 * 1024 * 1024) { overflow = true; proc.kill(); }
        else stdout += data.toString();
      });
      proc.stderr.on('data', data => { stderrBytes += data.length; if (stderrBytes > 256 * 1024) { overflow = true; proc.kill(); } });
      proc.on('error', () => reject(new Error('Python could not start. Check the configured Python executable and requirements.')));
      proc.on('close', code => {
        children.delete(proc);
        if (active === proc) active = null;
        if (proc.cancelled) return reject(new Error('Scan cancelled'));
        if (overflow) return reject(new Error('Python response exceeded the safety limit'));
        try {
          const result = JSON.parse(stdout);
          if (code !== 0 || result.success === false) throw new Error(result.error || 'Python request failed');
          resolve(result);
        } catch (err) { reject(new Error(`Python request failed: ${err.message}`)); }
      });
    });
  }
  function terminate(proc) {
    if (proc.stopPromise) return proc.stopPromise;
    proc.cancelled = true;
    proc.stopPromise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => { proc.kill('SIGKILL'); }, 3000);
      const deadline = setTimeout(() => reject(new Error('Python process did not exit after termination')), 6000);
      proc.once('close', () => { clearTimeout(timer); clearTimeout(deadline); resolve({ success: true }); });
      proc.kill();
    });
    return proc.stopPromise;
  }
  function stop() { return active ? terminate(active) : Promise.resolve({ success: false, message: 'No scan running' }); }
  async function shutdown() { closing = true; await Promise.all([...children].map(terminate)); }
  return { request, stop, shutdown };
}
module.exports = { createBridge };
