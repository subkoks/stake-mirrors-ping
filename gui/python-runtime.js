const path = require('node:path');
const fs = require('node:fs');
const { execFile } = require('node:child_process');
const { promisify } = require('node:util');
const execute = promisify(execFile);
const MINIMUMS = { aiohttp: '3.14.4', certifi: '2026.10.19', 'curl-cffi': '0.7', 'python-dotenv': '1.0', pydantic: '2.0', pyyaml: '6.0', rich: '13.0' };
const CHECK = 'import sys,json,re; sys.exit(12) if sys.version_info < (3,12) else None; import aiohttp,certifi,curl_cffi,dotenv,pydantic,yaml,rich; from importlib.metadata import version; numbers=lambda v: tuple(int(x) for x in re.match(r"[0-9]+(?:\\.[0-9]+)*",v).group().split(".")); sys.exit(13) if any(numbers(version(name)) < numbers(minimum) for name,minimum in json.loads(sys.argv[1]).items()) else None';

async function resolvePython({ packaged, resourceRoot, dataRoot, env = process.env, platform = process.platform, run = execute }) {
  const preference = path.join(dataRoot, 'python-path.txt');
  const configured = env.STAKE_PYTHON || (fs.existsSync(preference) ? fs.readFileSync(preference, 'utf8').trim() : null);
  if (configured && !path.isAbsolute(configured)) throw new Error('Python path must be an absolute executable path');
  const candidates = configured ? [configured] : [
    ...(!packaged ? [path.join(resourceRoot, '.venv', platform === 'win32' ? 'Scripts/python.exe' : 'bin/python')] : []),
    ...(platform === 'darwin' ? ['/opt/homebrew/bin/python3', '/usr/local/bin/python3'] : []),
    platform === 'win32' ? 'python' : 'python3',
  ];
  for (const candidate of [...new Set(candidates)]) {
    try {
      await run(candidate, ['-I', '-c', CHECK, JSON.stringify(MINIMUMS)], { timeout: 10000, maxBuffer: 8192, env, windowsHide: true });
      return candidate;
    } catch (_) { /* Never print interpreter stderr or inherited environment. */ }
  }
  throw new Error(`Python 3.12+ with the application requirements is required. Create a separate Python environment, install requirements.txt from the app resources, then put its absolute Python executable path in ${preference}. You can also launch with STAKE_PYTHON set to that path. Restart the app after configuring Python.`);
}
module.exports = { resolvePython, MINIMUMS };
