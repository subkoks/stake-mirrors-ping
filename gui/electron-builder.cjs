const fs = require('node:fs');
const path = require('node:path');
const { createHash } = require('node:crypto');
const manifest = require('./package.json');
const fixture = process.env.STAKE_DESKTOP_TEST === '1';
const target = `${process.platform}-${process.arch}`;
const backend = path.resolve(__dirname, '../packaging/output', fixture ? 'fixture' : 'production', target, 'stake-backend');
module.exports = {
  ...manifest.build,
  mac: { ...manifest.build.mac, hardenedRuntime: true, entitlements: '../packaging/entitlements.mac.plist', entitlementsInherit: '../packaging/entitlements.mac.plist' },
  extraMetadata: { desktopTest: fixture },
  extraResources: [{ from: '../config.yaml', to: 'config.yaml' }, { from: backend, to: 'backend' }],
  beforePack: async context => {
    const info = JSON.parse(fs.readFileSync(path.join(backend, 'provenance.json'), 'utf8'));
    const arch = { 1: 'x64', 3: 'arm64' }[context.arch];
    if (info.target !== `${context.electronPlatformName}-${arch}` || info.fixture !== fixture || info.version !== manifest.version) throw new Error('Backend OS, architecture, flavor or version does not match installer');
    if (!info.files || !Object.keys(info.files).length) throw new Error('Missing backend inventory');
    for (const [name, digest] of Object.entries(info.files)) {
      const file = path.resolve(backend, name);
      if (!file.startsWith(backend + path.sep) || !fs.realpathSync(file).startsWith(fs.realpathSync(backend) + path.sep) || createHash('sha256').update(fs.readFileSync(file)).digest('hex') !== digest) throw new Error('Backend inventory corruption: ' + name);
    }
  },
};
