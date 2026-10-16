// Downloaded maps are opened from disk (file://). Browsers send no Referer from
// there, so OpenStreetMap's volunteer tile servers block them ("403 Access
// blocked"). Swap the background for OpenFreeMap, which needs no Referer or API
// key, drawn with MapLibre through its Leaflet plugin. Online maps keep OSM.
function useOfflineBasemap(map) {
  if (window.location.protocol !== 'file:') return;

  const blocked = [];
  map.eachLayer(layer => {
    if (layer instanceof L.TileLayer && String(layer._url).includes('tile.openstreetmap.org')) {
      blocked.push(layer);
    }
  });
  if (!blocked.length) return;
  blocked.forEach(layer => map.removeLayer(layer));
  const restore = () => blocked.forEach(layer => layer.addTo(map));

  // MapLibre 5 is the newest release with a classic (non-module) build, which
  // the plugin needs and which works from file:// pages.
  const load = (tag, attributes) => new Promise((resolve, reject) => {
    const element = document.createElement(tag);
    Object.assign(element, attributes, { crossOrigin: 'anonymous', onload: resolve, onerror: reject });
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
    L.maplibreGL({ style: 'https://tiles.openfreemap.org/styles/liberty' }).addTo(map);
  }).catch(restore); // e.g. no internet or no WebGL: fall back to the original layer
}
