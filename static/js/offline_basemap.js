// Downloaded maps are opened from disk (file://). Browsers send no Referer from
// there, so OpenStreetMap's volunteer tile servers block them ("403 Access
// blocked"). Swap the background for OpenFreeMap, which needs no Referer or API
// key, drawn with MapLibre through its Leaflet plugin. Online maps keep OSM.
function useOfflineBasemap(map) {
  if (window.location.protocol !== 'file:') return;

  const isOsm = layer => layer instanceof L.TileLayer &&
                         String(layer._url).includes('tile.openstreetmap.org');
  const blocked = [];
  map.eachLayer(layer => { if (isOsm(layer)) blocked.push(layer); });
  if (!blocked.length) return;
  // OSM can't work from file:// in a normal browser, so it is not restored on
  // failure; a note explains instead of a map full of "Access blocked" tiles.
  blocked.forEach(layer => map.removeLayer(layer));
  // Folium can add a layer again later in its script (it does once per save),
  // so keep OSM off the map if it comes back.
  map.on('layeradd', event => { if (isOsm(event.layer)) map.removeLayer(event.layer); });

  let notice = null;
  const fail = (reason, detail) => {
    console.error('Offline background map failed: ' + reason, detail || '');
    if (notice) return;
    notice = L.control({ position: 'bottomleft' });
    notice.onAdd = () => {
      const box = L.DomUtil.create('div');
      box.setAttribute('role', 'status');
      box.style.cssText = 'background:white;padding:8px 10px;border-radius:6px;max-width:320px;' +
                          'font:12px Arial,sans-serif;box-shadow:0 1px 4px rgba(0,0,0,0.3)';
      box.textContent = 'The background map could not load in this downloaded copy (' + reason +
                        '). The route, pins, notes and files still work.';
      return box;
    };
    notice.addTo(map);
  };

  const probe = document.createElement('canvas');
  if (!(probe.getContext('webgl2') || probe.getContext('webgl'))) {
    fail('WebGL is unavailable: check that hardware acceleration is on in the browser settings');
    return;
  }

  // MapLibre 5 is the newest release with a classic (non-module) build, which
  // the plugin needs and which works from file:// pages.
  const load = (tag, attributes) => new Promise((resolve, reject) => {
    const element = document.createElement(tag);
    Object.assign(element, attributes, {
      crossOrigin: 'anonymous',
      onload: resolve,
      onerror: () => reject(new Error('could not download ' + (attributes.src || attributes.href)))
    });
    document.head.appendChild(element);
  });
  load('link', {
    rel: 'stylesheet',
    href: 'https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.css',
    integrity: 'sha384-uTttxo/aOKbdE5RlD/SPzSDoDmNvGlUYPjONi2MN/b7c9HPSvW07OIuyP7uL6jxK'
  }).catch(() => {});
  load('script', {
    src: 'https://cdn.jsdelivr.net/npm/maplibre-gl@5.24.0/dist/maplibre-gl.js',
    integrity: 'sha384-5+cfbwT0iiub6VsQAdn6yz16nr6sDiQoHx6tm4O8OVYXHYOxcffFmCJBL0dgdvGp'
  }).then(() => load('script', {
    src: 'https://cdn.jsdelivr.net/npm/@maplibre/maplibre-gl-leaflet@0.1.4/leaflet-maplibre-gl.js',
    integrity: 'sha384-tXYNKOHx4T02jMP7YYCtBxPIv1B5gaA5mcVPBzqMp6d7VzWzxJgI2aWF/nJLrQdS'
  })).then(() => {
    // Attribution (OpenFreeMap, OpenMapTiles, OpenStreetMap) comes from the style.
    const layer = L.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty' }).addTo(map);
    const glMap = layer.getMaplibreMap();
    // Style/tile download problems are reported as events, not exceptions.
    glMap.on('error', event => {
      const error = event && event.error;
      if (!glMap.isStyleLoaded()) fail((error && error.message) || 'the map style did not load', error);
      else console.warn('Offline background map:', error || event);
    });
  }).catch(error => fail((error && error.message) || String(error), error));
}
