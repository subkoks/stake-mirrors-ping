const path = require('node:path');
const fs = require('node:fs');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const { resolvePython } = require('./python-runtime');
const execute = promisify(execFile);

async function resolveBackend({ packaged, resourceRoot, dataRoot, version, platform = process.platform, arch = process.arch, testBuild = false, run = execute }) {
  if (!packaged) {
    const python = await resolvePython({ packaged: false, resourceRoot, dataRoot });
    return { executable: python, args: ['-I', path.join(resourceRoot, 'src/core/api.py')], kind: 'development' };
  }
  const root = path.join(resourceRoot, 'backend');
  const executable = path.join(root, platform === 'win32' ? 'stake-backend.exe' : 'stake-backend');
  try {
    const manifest = JSON.parse(fs.readFileSync(path.join(root, 'provenance.json'), 'utf8'));
    if (manifest.fixture !== testBuild || manifest.target !== `${platform}-${arch}` || manifest.version !== version) throw new Error('Backend manifest mismatch');
    const { stdout } = await run(executable, ['health'], {
      cwd: dataRoot, timeout: 20000, maxBuffer: 16384, windowsHide: true,
      env: backendEnvironment(process.env, dataRoot),
    });
    const health = JSON.parse(stdout);
    if (!health.success || !health.frozen || health.protocol !== 1 || health.architecture !== arch || health.version !== version) throw new Error('Backend health mismatch');
    return { executable, args: [], kind: 'bundled', health };
  } catch (_) {
    throw new Error('The bundled scan engine is missing, damaged, or incompatible. Retry, or reinstall the app from its official release page. Your saved settings and history are kept separately. Open the support folder for diagnostics.');
  }
}
function backendEnvironment(env, dataRoot) {
  const safe = { ...env, STAKE_DATA_DIR: dataRoot, PYTHONNOUSERSITE: '1', PYTHONUTF8: '1' };
  for (const key of Object.keys(safe)) {
    if (/^(PYTHON|STAKE_|VIRTUAL_ENV|CONDA_PREFIX|DYLD_|LD_PRELOAD)/.test(key) && !['STAKE_DATA_DIR', 'PYTHONNOUSERSITE', 'PYTHONUTF8'].includes(key)) delete safe[key];
  }
  return safe;
}
module.exports = { resolveBackend, backendEnvironment };
