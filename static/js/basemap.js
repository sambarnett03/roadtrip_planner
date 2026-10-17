// Background map for every generated map, online and downloaded: OpenFreeMap's
// "Liberty" style, drawn with MapLibre through its Leaflet plugin. It needs no
// API key or Referer, so it also works in downloaded maps opened from disk
// (file://), where OpenStreetMap's tile servers block requests ("403 Access
// blocked") because browsers send no Referer from there.
function addBasemap(map) {
  const offline = window.location.protocol === 'file:';
  let glLayer = null;
  let failed = false;

  const fail = (reason, detail) => {
    console.error('Background map failed: ' + reason, detail || '');
    if (failed) return;
    failed = true;
    if (glLayer) map.removeLayer(glLayer);
    if (!offline) {
      // Online pages send a Referer, so OpenStreetMap's own tiles work as a fallback.
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
      }).addTo(map);
      return;
    }
    // Downloaded copies have no working fallback, so explain instead.
    const notice = L.control({ position: 'bottomleft' });
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
    glLayer = L.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty' }).addTo(map);
    const glMap = glLayer.getMaplibreMap();
    // Style/tile download problems are reported as events, not exceptions.
    glMap.on('error', event => {
      const error = event && event.error;
      if (!glMap.isStyleLoaded()) fail((error && error.message) || 'the map style did not load', error);
      else console.warn('Background map:', error || event);
    });
  }).catch(error => fail((error && error.message) || String(error), error));
}
