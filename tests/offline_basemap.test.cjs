const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/js/offline_basemap.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function setup({ protocol = 'file:', failing = null, tileUrl = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png' } = {}) {
  class TileLayer {
    constructor(url) { this._url = url; }
    addTo(map) { map.layers.add(this); return this; }
  }
  const map = { layers: new Set(),
                eachLayer(callback) { [...this.layers].forEach(callback); },
                removeLayer(layer) { this.layers.delete(layer); } };
  const osm = new TileLayer(tileUrl).addTo(map);
  const marker = { kind: 'marker' };
  map.layers.add(marker);
  const loaded = [];
  const context = {
    window: { location: { protocol } },
    document: {
      createElement: tag => ({ tag }),
      head: { appendChild: element => {
        loaded.push(element);
        const url = element.src || element.href;
        setImmediate(() => (failing && url.includes(failing) ? element.onerror(new Error('blocked')) : element.onload()));
      } }
    },
    L: { TileLayer,
         maplibreGL: options => ({ options, addTo(m) { m.layers.add(this); return this; } }) }
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { map, osm, marker, loaded, run: () => context.useOfflineBasemap(map) };
}

const glLayers = map => [...map.layers].filter(layer => layer.options && layer.options.style);

test('online maps keep OpenStreetMap and load nothing extra', async () => {
  const s = setup({ protocol: 'https:' });
  s.run();
  await flush();
  assert.equal(s.loaded.length, 0);
  assert.ok(s.map.layers.has(s.osm));
});

test('downloaded maps swap OpenStreetMap for OpenFreeMap', async () => {
  const s = setup();
  s.run();
  // The blocked layer goes straight away; other layers (markers, routes) stay.
  assert.equal(s.map.layers.has(s.osm), false);
  assert.ok(s.map.layers.has(s.marker));
  for (let i = 0; i < 4; i++) await flush();

  const [css, maplibre, plugin] = s.loaded;
  assert.match(css.href, /maplibre-gl@5\.24\.0\/dist\/maplibre-gl\.css$/);
  assert.match(maplibre.src, /maplibre-gl@5\.24\.0\/dist\/maplibre-gl\.js$/);
  // The plugin needs MapLibre's global, so it loads after it.
  assert.match(plugin.src, /maplibre-gl-leaflet@0\.1\.4\/leaflet-maplibre-gl\.js$/);
  for (const element of s.loaded) {
    assert.match(element.integrity, /^sha384-/);
    assert.equal(element.crossOrigin, 'anonymous');
  }
  const [gl] = glLayers(s.map);
  assert.equal(gl.options.style, 'https://tiles.openfreemap.org/styles/liberty');
});

test('if MapLibre cannot load, the original layer comes back', async () => {
  for (const failing of ['maplibre-gl.js', 'leaflet-maplibre-gl.js']) {
    const s = setup({ failing });
    s.run();
    for (let i = 0; i < 4; i++) await flush();
    assert.ok(s.map.layers.has(s.osm), failing);
    assert.equal(glLayers(s.map).length, 0, failing);
  }
});

test('maps without OpenStreetMap tiles are left alone', async () => {
  const s = setup({ tileUrl: 'https://example.com/{z}/{x}/{y}.png' });
  s.run();
  await flush();
  assert.equal(s.loaded.length, 0);
  assert.ok(s.map.layers.has(s.osm));
});
