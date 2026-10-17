const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/js/offline_basemap.js'), 'utf8');
const flush = async (times = 4) => { for (let i = 0; i < times; i++) await new Promise(r => setImmediate(r)); };
const OSM = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';

function setup({ protocol = 'file:', failing = null, webgl = true, tileUrl = OSM } = {}) {
  const handlers = {};
  const map = {
    layers: new Set(),
    controls: [],
    eachLayer(callback) { [...this.layers].forEach(callback); },
    removeLayer(layer) { this.layers.delete(layer); },
    on(event, handler) { (handlers[event] = handlers[event] || []).push(handler); }
  };
  class TileLayer {
    constructor(url) { this._url = url; }
    addTo(target) {
      target.layers.add(this);
      (handlers.layeradd || []).forEach(handler => handler({ layer: this }));
      return this;
    }
  }
  const osm = new TileLayer(tileUrl).addTo(map);
  const marker = { kind: 'marker' };
  map.layers.add(marker);
  const loaded = [];
  const errors = [];
  const glEvents = {};
  const glMap = { styleLoaded: false, isStyleLoaded() { return this.styleLoaded; },
                  on(event, handler) { glEvents[event] = handler; } };
  const context = {
    console: { error: (...args) => errors.push(args.join(' ')), warn() {} },
    window: { location: { protocol } },
    document: {
      createElement: tag => (tag === 'canvas' ? { getContext: () => (webgl ? {} : null) } : { tag }),
      head: { appendChild: element => {
        loaded.push(element);
        const url = element.src || element.href;
        setImmediate(() => (failing && url.includes(failing) ? element.onerror(new Error('blocked')) : element.onload()));
      } }
    },
    L: {
      TileLayer,
      maplibreGL: options => ({ options, getMaplibreMap: () => glMap,
                                addTo(m) { m.layers.add(this); return this; } }),
      control: () => ({ addTo(m) { m.controls.push(this.onAdd(m)); return this; } }),
      DomUtil: { create: () => ({ style: {}, setAttribute() {} }) }
    }
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { map, osm, marker, loaded, errors, glMap, glEvents, TileLayer,
           run: () => context.useOfflineBasemap(map) };
}

const glLayers = map => [...map.layers].filter(layer => layer.options && layer.options.style);
const noteText = map => map.controls.map(box => box.textContent).join('');

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
  await flush();

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
  assert.equal(s.map.controls.length, 0);
  assert.deepEqual(s.errors, []);
});

test('OpenStreetMap is removed again if it is re-added later', async () => {
  // folium adds the tile layer again at the end of its script on later saves.
  const s = setup();
  s.run();
  s.osm.addTo(s.map);
  assert.equal(s.map.layers.has(s.osm), false);
  const other = new s.TileLayer('https://example.com/{z}/{x}/{y}.png').addTo(s.map);
  assert.ok(s.map.layers.has(other));
});

test('failures show a note instead of restoring the blocked tiles', async () => {
  for (const failing of ['maplibre-gl.js', 'leaflet-maplibre-gl.js']) {
    const s = setup({ failing });
    s.run();
    await flush();
    assert.equal(s.map.layers.has(s.osm), false, failing);
    assert.equal(glLayers(s.map).length, 0, failing);
    assert.match(noteText(s.map), /could not download .*\. The route, pins, notes and files still work\./, failing);
    assert.match(s.errors[0], /Offline background map failed/, failing);
  }
});

test('missing WebGL is explained without downloading MapLibre', async () => {
  const s = setup({ webgl: false });
  s.run();
  await flush();
  assert.equal(s.loaded.length, 0);
  assert.equal(s.map.layers.has(s.osm), false);
  assert.match(noteText(s.map), /WebGL is unavailable: check that hardware acceleration is on/);
});

test('a style that fails to load is reported; later tile errors are not', async () => {
  const s = setup();
  s.run();
  await flush();
  s.glEvents.error({ error: new Error('style request failed') });
  assert.match(noteText(s.map), /style request failed/);
  const t = setup();
  t.run();
  await flush();
  t.glMap.styleLoaded = true;
  t.glEvents.error({ error: new Error('one tile failed') });
  assert.equal(t.map.controls.length, 0);
});

test('maps without OpenStreetMap tiles are left alone', async () => {
  const s = setup({ tileUrl: 'https://example.com/{z}/{x}/{y}.png' });
  s.run();
  await flush();
  assert.equal(s.loaded.length, 0);
  assert.ok(s.map.layers.has(s.osm));
});
