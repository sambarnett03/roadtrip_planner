const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/js/basemap.js'), 'utf8');
const flush = async (times = 4) => { for (let i = 0; i < times; i++) await new Promise(r => setImmediate(r)); };

function setup({ protocol = 'https:', failing = null, webgl = true } = {}) {
  const map = {
    layers: new Set(),
    controls: [],
    removeLayer(layer) { this.layers.delete(layer); }
  };
  const loaded = [];
  const errors = [];
  const glEvents = {};
  const glMap = { styleLoaded: false, isStyleLoaded() { return this.styleLoaded; },
                  on(event, handler) { glEvents[event] = handler; } };
  const layer = props => ({ ...props, addTo(m) { m.layers.add(this); return this; } });
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
      maplibreGL: options => layer({ kind: 'gl', options, getMaplibreMap: () => glMap }),
      tileLayer: (url, options) => layer({ kind: 'tiles', url, options }),
      control: () => ({ addTo(m) { m.controls.push(this.onAdd(m)); return this; } }),
      DomUtil: { create: () => ({ style: {}, setAttribute() {} }) }
    }
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  return { map, loaded, errors, glMap, glEvents, run: () => context.addBasemap(map) };
}

const ofKind = (map, kind) => [...map.layers].filter(layer => layer.kind === kind);
const osm = map => ofKind(map, 'tiles').filter(layer => layer.url.includes('tile.openstreetmap.org'));
const noteText = map => map.controls.map(box => box.textContent).join('');

for (const protocol of ['https:', 'file:']) {
  test(`${protocol} maps get the OpenFreeMap background and no OpenStreetMap tiles`, async () => {
    const s = setup({ protocol });
    s.run();
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
    const [gl] = ofKind(s.map, 'gl');
    assert.equal(gl.options.style, 'https://tiles.openfreemap.org/styles/liberty');
    assert.equal(osm(s.map).length, 0);
    assert.equal(s.map.controls.length, 0);
    assert.deepEqual(s.errors, []);
  });
}

test('online, a failed download falls back to OpenStreetMap tiles', async () => {
  for (const failing of ['maplibre-gl.js', 'leaflet-maplibre-gl.js']) {
    const s = setup({ failing });
    s.run();
    await flush();
    const [tiles] = osm(s.map);
    assert.ok(tiles, failing);
    assert.match(tiles.options.attribution, /OpenStreetMap<\/a> contributors/);
    assert.equal(s.map.controls.length, 0, failing);
    assert.match(s.errors[0], /Background map failed/);
  }
});

test('downloaded copies explain a failure instead of using blocked OpenStreetMap tiles', async () => {
  const s = setup({ protocol: 'file:', failing: 'maplibre-gl.js' });
  s.run();
  await flush();
  assert.equal(osm(s.map).length, 0);
  assert.match(noteText(s.map), /could not download .*\. The route, pins, notes and files still work\./);
});

test('missing WebGL skips MapLibre: OpenStreetMap online, a note offline', async () => {
  const online = setup({ webgl: false });
  online.run();
  await flush();
  assert.equal(online.loaded.length, 0);
  assert.equal(osm(online.map).length, 1);
  const offline = setup({ protocol: 'file:', webgl: false });
  offline.run();
  await flush();
  assert.equal(offline.loaded.length, 0);
  assert.match(noteText(offline.map), /WebGL is unavailable: check that hardware acceleration is on/);
});

test('a style that fails to load replaces the blank MapLibre layer; later tile errors do not', async () => {
  const s = setup();
  s.run();
  await flush();
  s.glEvents.error({ error: new Error('style request failed') });
  assert.equal(ofKind(s.map, 'gl').length, 0);
  assert.equal(osm(s.map).length, 1);
  // Only one fallback, however many errors arrive.
  s.glEvents.error({ error: new Error('style request failed again') });
  assert.equal(osm(s.map).length, 1);

  const t = setup();
  t.run();
  await flush();
  t.glMap.styleLoaded = true;
  t.glEvents.error({ error: new Error('one tile failed') });
  assert.equal(ofKind(t.map, 'gl').length, 1);
  assert.equal(osm(t.map).length, 0);
});
