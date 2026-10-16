const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync(require('node:path').join(__dirname, '../static/js/encrypted_notes.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function setup(extra = {}) {
  const elements = [];
  const storage = new Map();
  const timers = new Map();
  const calls = [];
  let timerId = 0;
  let snapshot;
  let authChange;
  let beforeUnload;
  const state = { text: '<b>Original</b>', revision: 'r1', can_edit: true };
  let handler = async (method, body) => {
    if (method === 'POST') {
      state.text = body.text;
      state.revision = 'r2';
    }
    return { ok: true, json: async () => ({ ...state }) };
  };
  const context = {
    document: { createElement: () => {
      const element = { style: {}, setAttribute() {}, after() {} };
      elements.push(element);
      return element;
    } },
    window: { addEventListener: (_, callback) => { beforeUnload = callback; } },
    localStorage: { getItem: key => storage.get(key) || null,
                    setItem: (key, value) => storage.set(key, value) },
    URLSearchParams,
    fetch: async (_, options) => {
      const body = options.body ? JSON.parse(options.body) : null;
      calls.push({ ...options, body });
      return handler(options.method, body);
    },
    setTimeout: callback => { timers.set(++timerId, callback); return timerId; },
    clearTimeout: id => timers.delete(id)
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  const editableDiv = { innerHTML: '', after() {} };
  const toggle = { checked: true };
  const auth = { currentUser: { getIdToken: async () => 'firebase-token' },
                 onAuthStateChanged: callback => { authChange = callback; } };
  const docRef = { onSnapshot: callback => { snapshot = callback; return () => {}; } };
  const controller = context.createEncryptedNotes({ auth, docRef, editableDiv, toggle,
                                                  ownerId: 'owner', mapId: 'trip', ...extra });
  return { controller, editableDiv, toggle, calls, state, storage, auth,
           status: elements[0], retry: elements[1],
           setHandler: callback => { handler = callback; },
           snapshot: () => snapshot(), authChange: () => authChange(),
           beforeUnload: event => beforeUnload(event),
           runTimers: () => {
             const pending = [...timers.values()];
             timers.clear();
             pending.forEach(callback => callback());
           } };
}

async function load(s) {
  s.controller.loadShared();
  await flush();
}
function type(s, html) {
  s.editableDiv.innerHTML = html;
  s.editableDiv.oninput();
}

test('shared notes stay locked until decrypted and use Firebase tokens without cookies', async () => {
  const s = setup();
  s.controller.loadShared();
  assert.equal(s.editableDiv.contentEditable, 'false');
  assert.equal(s.editableDiv.oninput, null);
  await flush();
  assert.equal(s.editableDiv.innerHTML, '<b>Original</b>');
  assert.equal(s.editableDiv.contentEditable, 'true');
  assert.equal(s.calls[0].credentials, 'omit');
  assert.equal(s.calls[0].headers.Authorization, 'Bearer firebase-token');
  assert.equal(s.calls.filter(call => call.method === 'POST').length, 0);
});

test('saving serializes edits typed while a previous save is pending', async () => {
  const s = setup();
  await load(s);
  let finishSave;
  s.setHandler((method, body) => {
    if (method === 'POST') return new Promise(resolve => { finishSave = () => {
      Object.assign(s.state, { text: body.text, revision: 'r2' });
      resolve({ ok: true, json: async () => ({ revision: 'r2' }) });
    }; });
    return { ok: true, json: async () => ({ ...s.state }) };
  });
  type(s, 'First edit');
  s.runTimers();
  await flush();
  type(s, 'Second edit');
  s.snapshot();
  assert.equal(s.editableDiv.innerHTML, 'Second edit');
  finishSave();
  await flush();
  s.runTimers();
  await flush();
  const saves = s.calls.filter(call => call.method === 'POST');
  assert.equal(saves.length, 2);
  assert.equal(saves[0].body.revision, 'r1');
  assert.equal(saves[1].body.revision, 'r2');
  assert.equal(saves[1].body.text, 'Second edit');
  finishSave();
  await flush();
  assert.equal(s.status.textContent, 'Saved');
});

test('a conflict retains unsaved edits and prevents further writes', async () => {
  const s = setup();
  await load(s);
  s.setHandler(async () => ({ ok: false, status: 409,
                             json: async () => ({ error: 'Copy your edits, then reload.' }) }));
  type(s, 'Keep this draft');
  s.runTimers();
  await flush();
  assert.equal(s.editableDiv.innerHTML, 'Keep this draft');
  assert.equal(s.editableDiv.contentEditable, 'false');
  assert.match(s.status.textContent, /unsaved edits/);
  s.toggle.checked = false;
  s.controller.loadPersonal();
  assert.equal(s.toggle.checked, true);
  let warned = false;
  s.beforeUnload({ preventDefault() { warned = true; } });
  assert.equal(warned, true);
});

test('a missing key cannot enable editing or save an empty replacement', async () => {
  const s = setup();
  s.setHandler(async () => ({ ok: false, status: 503,
                             json: async () => ({ error: 'Check the encryption key.' }) }));
  await load(s);
  assert.equal(s.editableDiv.contentEditable, 'false');
  assert.equal(s.editableDiv.oninput, null);
  assert.match(s.status.textContent, /encryption key/);
  assert.equal(s.calls.some(call => call.method === 'POST'), false);
});

test('live updates refresh clean editors and preserve unsaved drafts', async () => {
  const s = setup();
  await load(s);
  Object.assign(s.state, { text: 'Remote edit', revision: 'remote' });
  s.snapshot();
  await flush();
  assert.equal(s.editableDiv.innerHTML, 'Remote edit');
  type(s, 'My draft');
  Object.assign(s.state, { text: 'Another remote edit', revision: 'remote2' });
  s.snapshot();
  await flush();
  assert.equal(s.editableDiv.innerHTML, 'My draft');
});

test('viewers cannot type, and personal notes retain the existing local storage key', async () => {
  const s = setup();
  s.state.can_edit = false;
  await load(s);
  assert.equal(s.editableDiv.contentEditable, 'false');
  assert.equal(s.editableDiv.oninput, null);
  s.storage.set('personalText_trip', '<i>Old personal note</i>');
  s.toggle.checked = false;
  s.controller.loadPersonal();
  assert.equal(s.editableDiv.innerHTML, '<i>Old personal note</i>');
  type(s, 'Updated personal note');
  assert.equal(s.storage.get('personalText_trip'), 'Updated personal note');
  assert.equal(s.calls.some(call => call.method === 'POST'), false);
});

test('a delayed live read cannot revert a save completed while the read was pending', async () => {
  const s = setup();
  await load(s);
  let finishRead;
  let firstRead = true;
  s.setHandler(async (method, body) => {
    if (method === 'POST') {
      Object.assign(s.state, { text: body.text, revision: 'saved' });
      return { ok: true, json: async () => ({ revision: 'saved' }) };
    }
    if (firstRead) {
      firstRead = false;
      return new Promise(resolve => { finishRead = () => resolve({ ok: true,
        json: async () => ({ text: 'Stale response', revision: 'old', can_edit: true }) }); });
    }
    return { ok: true, json: async () => ({ ...s.state }) };
  });
  s.snapshot();
  await flush();
  type(s, 'New saved text');
  s.runTimers();
  await flush();
  finishRead();
  await flush();
  assert.equal(s.editableDiv.innerHTML, 'New saved text');
});

test('downloaded maps show the saved shared note read-only without contacting the server', async () => {
  const s = setup({ auth: null, docRef: null, offlineNotes: { text: '<b>Saved copy</b>' },
                    savedAt: '2026-10-17T10:00:00+00:00' });
  await load(s);
  assert.equal(s.editableDiv.innerHTML, '<b>Saved copy</b>');
  assert.equal(s.editableDiv.contentEditable, 'false');
  assert.equal(s.editableDiv.oninput, null);
  assert.match(s.status.textContent, /Copy of the shared notes saved .*Open the map online/);
  assert.equal(s.calls.length, 0);
  // Personal notes still work in the downloaded file.
  s.toggle.checked = false;
  s.controller.loadPersonal();
  assert.equal(s.editableDiv.contentEditable, 'true');
  type(s, 'Offline personal note');
  assert.equal(s.storage.get('personalText_trip'), 'Offline personal note');
  s.toggle.checked = true;
  await load(s);
  assert.equal(s.editableDiv.innerHTML, '<b>Saved copy</b>');
  assert.equal(s.calls.length, 0);
});

test('downloaded maps explain when the shared notes could not be included', async () => {
  const s = setup({ auth: null, docRef: null,
                    offlineNotes: { error: 'Shared notes could not be included in this download.' } });
  await load(s);
  assert.equal(s.editableDiv.innerHTML, '');
  assert.equal(s.editableDiv.contentEditable, 'false');
  assert.equal(s.status.textContent, 'Shared notes could not be included in this download.');
  assert.equal(s.calls.length, 0);
});
