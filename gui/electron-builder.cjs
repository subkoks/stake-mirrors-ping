const fs = require('node:fs');
const path = require('node:path');
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
  },
};
