const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/js/map_download.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));
const SERVER_HTML = '<html><head><script>window.ROADTRIP_OFFLINE = {"pdfs": []};</script>\n</head><body>Map</body></html>';

function setup({ personal = '<b>Mine</b>', response } = {}) {
  let clickHandler;
  const saved = [];
  const blobs = new Map();
  const storage = new Map(personal == null ? [] : [['personalText_trip', personal]]);
  const fetches = [];
  const context = {
    JSON, String, RegExp,
    document: {
      addEventListener: (type, handler) => { if (type === 'click') clickHandler = handler; },
      createElement: () => ({ remove() {}, click() { saved.push({ href: this.href, download: this.download }); } }),
      body: { append() {} }
    },
    localStorage: { getItem: key => (storage.has(key) ? storage.get(key) : null) },
    fetch: async (url, options) => {
      fetches.push({ url, options });
      return response || { ok: true, redirected: false, text: async () => SERVER_HTML,
                           headers: { get: () => 'attachment; filename=my_roadtrip.html' } };
    },
    Blob: class { constructor(parts, options) { this.text = parts.join(''); this.type = options.type; } },
    URL: { createObjectURL: blob => { const url = 'blob:' + blobs.size; blobs.set(url, blob); return url; },
           revokeObjectURL() {} },
    setTimeout: () => 0,
    window: { location: { href: 'https://site/map/trip' } }
  };
  vm.createContext(context);
  vm.runInContext(source, context);
  context.attachPersonalNotesToDownload('trip');
  const link = { href: '/download_current_map', textContent: 'Download map', dataset: {} };
  const click = async (extra = {}) => {
    const event = { target: { closest: () => link }, button: 0, defaultPrevented: false,
                    prevented: false, preventDefault() { this.prevented = true; }, ...extra };
    await clickHandler(event);
    await flush();
    return event;
  };
  return { context, click, saved, blobs, fetches, link };
}

function personalFrom(html) {
  const match = /window\.ROADTRIP_OFFLINE\.personal = (.*?);<\/script>/.exec(html);
  return match && JSON.parse(match[1]);
}

test('download adds this browser\'s personal notes to the server file', async () => {
  const s = setup();
  const event = await s.click();
  assert.equal(event.prevented, true);
  assert.equal(s.fetches[0].url, '/download_current_map');
  assert.equal(s.fetches[0].options.credentials, 'same-origin');
  assert.equal(s.saved.length, 1);
  assert.equal(s.saved[0].download, 'my_roadtrip.html');
  const html = s.blobs.get(s.saved[0].href).text;
  assert.equal(personalFrom(html), '<b>Mine</b>');
  // Inserted after the server's snapshot so it can extend it.
  assert.ok(html.indexOf('ROADTRIP_OFFLINE = ') < html.indexOf('ROADTRIP_OFFLINE.personal'));
  assert.ok(html.indexOf('ROADTRIP_OFFLINE.personal') < html.indexOf('</head>'));
  assert.equal(s.link.textContent, 'Download map');
});

test('personal notes cannot break out of the embedding script', async () => {
  const tricky = 'a </script><script>alert(1)</script> &   é';
  const s = setup({ personal: tricky });
  await s.click();
  const html = s.blobs.get(s.saved[0].href).text;
  assert.equal(personalFrom(html), tricky);
  assert.equal(html.includes('</script><script>alert(1)'), false);
});

test('no personal notes is recorded as null', async () => {
  const s = setup({ personal: null });
  await s.click();
  assert.equal(personalFrom(s.blobs.get(s.saved[0].href).text), null);
});

test('server errors fall back to the plain download so the error page shows', async () => {
  for (const response of [{ ok: false, redirected: false }, { ok: true, redirected: true }]) {
    const s = setup({ response });
    await s.click();
    assert.equal(s.saved.length, 0);
    assert.equal(s.context.window.location.href, '/download_current_map');
    assert.equal(s.link.textContent, 'Download map');
  }
});

test('modified clicks are left to the browser', async () => {
  const s = setup();
  const event = await s.click({ ctrlKey: true });
  assert.equal(event.prevented, false);
  assert.equal(s.fetches.length, 0);
});
