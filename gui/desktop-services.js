const fs = require('node:fs');
const path = require('node:path');
const https = require('node:https');
const RELEASE = 'https://github.com/subkoks/stake-mirrors-ping/releases';
function releaseURL(value) {
  const url = new URL(value);
  if (url.origin !== 'https://github.com' || !/^\/subkoks\/stake-mirrors-ping\/releases(?:\/tag\/v\d+\.\d+\.\d+)?$/.test(url.pathname) || url.username || url.password || url.search || url.hash) throw new Error('Unexpected release link');
  return url.href;
}
function mirrorURL(value, config) {
  if (typeof value !== 'string' || value.length > 2048) throw new Error('Invalid mirror');
  const url = new URL(value);
  if (url.protocol !== 'https:' || url.username || url.password || url.port || url.search || url.hash || url.pathname !== '/') throw new Error('Unsupported mirror link');
  const listed = config.mirrors.some(m => new URL(m.url).href === url.href && m.domain.toLowerCase() === url.hostname);
  if (!listed || url.hostname === 'localhost' || /^[\d.]+$/.test(url.hostname) || url.hostname.includes(':') || !url.hostname.includes('.')) throw new Error('Mirror is not configured');
  return url.href;
}
function latestRelease() {
  return new Promise((resolve, reject) => {
    const request = https.get('https://api.github.com/repos/subkoks/stake-mirrors-ping/releases/latest', { headers: { 'User-Agent': 'Stake-Mirrors-Ping', Accept: 'application/vnd.github+json' }, timeout: 10000 }, response => {
      let body = ''; let size = 0;
      response.on('data', chunk => { size += chunk.length; if (size > 128 * 1024) response.destroy(new Error('Update response too large')); else body += chunk.toString(); });
      response.on('error', reject);
      response.on('end', () => {
        try {
          if (response.statusCode !== 200) throw new Error('Update service is temporarily unavailable. Try again later.');
          const data = JSON.parse(body);
          if (data.draft || data.prerelease || !/^v\d+\.\d+\.\d+$/.test(data.tag_name)) throw new Error('No supported release information');
          resolve({ version: data.tag_name.slice(1), url: releaseURL(data.html_url) });
        } catch (error) { reject(error); }
      });
    });
    request.on('timeout', () => request.destroy(new Error('Update check timed out. Check your internet connection and retry.')));
    request.on('error', reject);
  });
}
function newer(candidate, current) {
  const a = candidate.split('.').map(Number), b = current.split('.').map(Number);
  for (let i = 0; i < 3; i++) { if (a[i] !== b[i]) return a[i] > b[i]; }
  return false;
}
function support(dataRoot, info) {
  const folder = path.join(dataRoot, 'support');
  fs.mkdirSync(folder, { recursive: true });
  // An allowlist deliberately excludes user paths, environment, tokens, configuration and scan data.
  function summary() { return JSON.stringify({ app: 'Stake Mirrors Ping', version: info.version, platform: process.platform, architecture: process.arch, backend: info.backend || 'not ready', lastIssue: info.issue || 'none' }, null, 2); }
  function record(issue) {
    info.issue = issue; // Callers supply fixed diagnostic codes, never raw exception text.
    const file = path.join(folder, 'diagnostics.log');
    if (fs.existsSync(file) && fs.statSync(file).size > 128 * 1024) fs.renameSync(file, path.join(folder, 'diagnostics.previous.log'));
    fs.appendFileSync(file, `${new Date().toISOString()} ${issue}\n`);
  }
  fs.writeFileSync(path.join(folder, 'README.txt'), 'Support diagnostics contain app/runtime details and fixed error codes only. Settings and history remain in the parent directory. Never send account tokens or personal scan data.\n');
  return { folder, summary, record };
}
module.exports = { releaseURL, mirrorURL, latestRelease, newer, support, RELEASE };
