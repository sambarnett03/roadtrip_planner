const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

class Element {
  constructor() { this.style = {}; this.children = []; this.events = {}; }
  append(...children) { this.children.push(...children); }
  setAttribute() {}
  addEventListener(event, handler) { this.events[event] = handler; }
  querySelector(selector) {
    for (const child of this.children) {
      if ('.' + child.className === selector) return child;
      const found = child.querySelector?.(selector);
      if (found) return found;
    }
    return null;
  }
  matches() { return !!this.hovered; }
  contains(element) { return this.children.includes(element); }
}

function setup({ included = false, canEdit = true, offline = false } = {}) {
  const popup = new Element();
  const content = new Element();
  content.className = 'leaflet-popup-content';
  popup.append(content);
  // folium passes Leaflet a content element; popup.update() rebuilds
  // .leaflet-popup-content from it, discarding anything appended alongside.
  const foliumContent = new Element();
  content.append(foliumContent);
  const events = {};
  let open = false;
  const marker = {
    on(event, callback) { events[event] = callback; },
    openPopup() { if (!open) { open = true; events.popupopen(); } },
    closePopup() { open = false; events.popupclose(); },
    getPopup: () => ({ getElement: () => popup, getContent: () => foliumContent,
                       update() { content.children = [foliumContent]; } })
  };
  const timers = new Map();
  let nextTimer = 0;
  const storage = new Map();
  const calls = [];
  let reloads = 0;
  let restored;
  let response = { ok: true, json: async () => ({ status: 'ok' }) };
  const context = {
    document: { createElement: () => new Element(), createTextNode: text => ({ text }), activeElement: null },
    window: { location: { protocol: offline ? 'file:' : 'http:', reload() { reloads++; } } },
    sessionStorage: { getItem: key => storage.get(key) || null, removeItem: key => storage.delete(key),
                      setItem: (key, value) => storage.set(key, value) },
    L: { DomEvent: { disableClickPropagation() {} } },
    setTimeout: fn => { timers.set(++nextTimer, fn); return nextTimer; },
    clearTimeout: id => timers.delete(id),
    fetch: async (url, options) => { calls.push({ url, ...options }); return response; }
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(__dirname, '../static/js/map_drive_controls.js'), 'utf8'), context);
  const map = { getCenter: () => ({ lat: 51.5, lng: -0.1 }), getZoom: () => 11,
                setView: (...args) => { restored = args; } };
  const attach = () => context.attachDriveControls(map,
    [{ marker, doc_id: 'actual-firestore-document', included }],
    { map_id: 'trip', owner_id: 'owner', can_edit: canEdit });
  attach();
  const hover = () => events.mouseover();
  const checkbox = () => popup.querySelector('.drive-control').children[0].children[0];
  return { hover, events, popup, checkbox, calls, storage, attach,
           get open() { return open; }, get reloads() { return reloads; }, get restored() { return restored; },
           setResponse(value) { response = value; },
           flushClose() { const pending = [...timers.values()]; timers.clear(); pending.forEach(fn => fn()); } };
}

test('hover panel stays open when moving from the marker onto the controls', () => {
  const s = setup();
  s.hover();
  assert.equal(s.open, true);
  s.events.mouseout();
  s.popup.onmouseenter();
  s.flushClose();
  assert.equal(s.open, true);
  s.popup.onmouseleave();
  s.flushClose();
  assert.equal(s.open, false);
});

test('click/tap pins the panel open and repeated hovers do not duplicate controls', () => {
  const s = setup();
  s.events.click();
  s.events.mouseout();
  s.flushClose();
  assert.equal(s.open, true);
  s.hover();
  assert.equal(s.popup.querySelector('.leaflet-popup-content').children.length, 1);
});

test('adding a stop saves its document ID, refreshes the route, and restores map position', async () => {
  const s = setup();
  s.hover();
  const checkbox = s.checkbox();
  checkbox.checked = true;
  await checkbox.events.change();
  assert.equal(s.calls.length, 1);
  assert.equal(s.calls[0].url, '/api/stops/update');
  assert.deepEqual(JSON.parse(s.calls[0].body), { map_id: 'trip', owner_id: 'owner', can_edit: true,
    doc_id: 'actual-firestore-document', field: 'drive', value: 'y' });
  assert.equal(s.reloads, 1);
  s.attach();
  assert.deepEqual(JSON.parse(JSON.stringify(s.restored)), [[51.5, -0.1], 11, { animate: false }]);
  assert.equal(s.storage.size, 0);
});

test('removing a driving stop saves n', async () => {
  const s = setup({ included: true });
  s.hover();
  assert.equal(s.checkbox().checked, true);
  s.checkbox().checked = false;
  await s.checkbox().events.change();
  assert.equal(JSON.parse(s.calls[0].body).value, 'n');
});

test('failed saves restore the checkbox and keep the map available for retry', async () => {
  const s = setup();
  s.hover();
  s.setResponse({ ok: false, json: async () => ({ error: 'access denied' }) });
  s.checkbox().checked = true;
  await s.checkbox().events.change();
  assert.equal(s.checkbox().checked, false);
  assert.equal(s.checkbox().disabled, false);
  assert.equal(s.reloads, 0);
  assert.equal(s.popup.querySelector('.drive-control').children[1].textContent, 'access denied');
});

test('viewers and downloaded maps show disabled toggles', () => {
  for (const options of [{ canEdit: false }, { offline: true }]) {
    const s = setup(options);
    s.hover();
    assert.equal(s.checkbox().disabled, true);
    assert.equal(s.calls.length, 0);
  }
});

test('expired login redirects cannot be mistaken for a successful save', async () => {
  const s = setup();
  s.hover();
  s.setResponse({ redirected: true });
  s.checkbox().checked = true;
  await s.checkbox().events.change();
  assert.equal(s.checkbox().checked, false);
  assert.equal(s.reloads, 0);
  assert.match(s.popup.querySelector('.drive-control').children[1].textContent, /sign in again/);
});
