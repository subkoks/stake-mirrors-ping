const { StringDecoder } = require('node:string_decoder');
function createBridge(spawn, pythonPath, scriptPath, options = {}, prefixArgs = null, onProgress = () => {}) {
  let active = null;
  let closing = false;
  const children = new Set();
  function request(command, config, scan = false) {
    if (closing) return Promise.reject(new Error('Application is shutting down'));
    if (scan && active) return Promise.reject(new Error('A scan is already running'));
    return new Promise((resolve, reject) => {
      const streaming = prefixArgs !== null && scan;
      const args = [...(prefixArgs ?? ['-I', scriptPath]), command, JSON.stringify(config || {}), ...(streaming ? ['--stream'] : [])];
      const proc = spawn(pythonPath, args, options);
      children.add(proc);
      if (scan) active = proc;
      let stdout = '';
      let stderrBytes = 0;
      const decoder = new StringDecoder('utf8');
      let pending = '';
      let totalBytes = 0;
      let resultMessage;
      let invalid = false;
      let overflow = false;
      proc.stdout.on('data', data => {
        totalBytes += data.length;
        if (totalBytes > 4 * 1024 * 1024) { overflow = true; proc.kill(); return; }
        const chunk = decoder.write(data);
        if (!streaming) { stdout += chunk; return; }
        pending += chunk;
        let newline;
        while ((newline = pending.indexOf('\n')) !== -1) {
          const line = pending.slice(0, newline); pending = pending.slice(newline + 1);
          if (!line.trim()) continue;
          try {
            const message = JSON.parse(line);
            if (message.type === 'result' && !resultMessage) resultMessage = message.data;
            else if (message.type === 'progress' && !resultMessage && !proc.cancelled && active === proc &&
              typeof message.stage === 'string' && message.stage.length <= 120 &&
              Number.isSafeInteger(message.completed) && Number.isSafeInteger(message.total) &&
              message.total >= 0 && message.total <= 10000 && message.completed >= 0 && message.completed <= message.total) {
              onProgress({ stage: message.stage, completed: message.completed, total: message.total });
            } else invalid = true;
          } catch (_) { invalid = true; }
        }
      });
      proc.stderr.on('data', data => { stderrBytes += data.length; if (stderrBytes > 256 * 1024) { overflow = true; proc.kill(); } });
      proc.on('error', () => reject(new Error('The scan engine could not start. Retry or reinstall the application.')));
      proc.on('close', code => {
        children.delete(proc);
        if (active === proc) active = null;
        if (proc.cancelled) return reject(new Error('Scan cancelled'));
        if (overflow) return reject(new Error('Scan engine response exceeded the safety limit'));
        try {
          if (invalid || (streaming && pending.trim())) throw new Error('Invalid scan engine message');
          const result = streaming ? resultMessage : JSON.parse(stdout + decoder.end());
          if (!result) throw new Error('Scan engine returned no result');
          if (code !== 0 || result.success === false) throw new Error(result.error || 'Scan engine request failed');
          resolve(result);
        } catch (err) { reject(new Error(`Scan engine request failed: ${err.message}`)); }
      });
    });
  }
  function terminate(proc) {
    if (proc.stopPromise) return proc.stopPromise;
    proc.cancelled = true;
    proc.stopPromise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => { proc.kill('SIGKILL'); }, 3000);
      const deadline = setTimeout(() => reject(new Error('Scan engine process did not exit after termination')), 6000);
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
