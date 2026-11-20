const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

let factory;
const context = {
  console,
  URLSearchParams,
  localStorage: { getItem: () => null, setItem: () => {} },
  document: { addEventListener: (_event, callback) => callback() },
  Alpine: { data: (_name, componentFactory) => { factory = componentFactory; } },
  window: { location: { pathname: '/devices', search: '' } },
  setTimeout,
  clearTimeout,
  setInterval,
  clearInterval
};

const jsFiles = [
  'app/static/js/utils.js',
  'app/static/js/modules/auth.js',
  'app/static/js/modules/devices.js',
  'app/static/js/modules/mesh.js',
  'app/static/js/modules/dns.js',
  'app/static/js/modules/automations.js',
  'app/static/js/modules/diagnostics.js',
  'app/static/js/app.js'
];
for (const file of jsFiles) {
  vm.runInNewContext(fs.readFileSync(file, 'utf8'), context);
}

const app = factory();
const expectedUrl = '/devices?search=%F0%9F%93%B1+Sala&band=5GHz&node=eero_01_gateway&category=Server%2FRete&profile=prof_01&assignment=dhcp&connected=true';

context.window.location.search = expectedUrl.slice(expectedUrl.indexOf('?'));
app.loadDeviceFiltersFromUrl();

assert.equal(app.deviceSearchQuery, '📱 Sala');
assert.equal(app.selectedCategoryFilter, 'Server/Rete');
assert.equal(app.showConnectedOnly, true);
assert.equal(app.deviceFiltersUrl(), expectedUrl);
console.log('device filter URL round-trip passed');
