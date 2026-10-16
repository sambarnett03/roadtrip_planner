// Personal notes live only in this browser's localStorage, so they are added to
// the downloaded map here instead of being sent to the server.
function withPersonalNotes(html, personal) {
  // Escape characters that could end the <script> early or break JS parsing.
  const json = JSON.stringify(personal == null ? null : String(personal))
    .replace(/</g, '\\u003c').replace(/>/g, '\\u003e').replace(/&/g, '\\u0026')
    .replace(/\u2028/g, '\\u2028').replace(/\u2029/g, '\\u2029');
  // Runs after the server's window.ROADTRIP_OFFLINE snapshot, which is also in <head>.
  // "<\/script>": this file is embedded inline, and a literal close tag would end it.
  const script = '<script>if (window.ROADTRIP_OFFLINE) window.ROADTRIP_OFFLINE.personal = ' +
                 json + ';<\/script>\n';
  const at = html.indexOf('</head>');
  return at === -1 ? script + html : html.slice(0, at) + script + html.slice(at);
}

function downloadName(response) {
  const match = /filename="?([^";]+)"?/.exec(response.headers.get('Content-Disposition') || '');
  return match ? match[1] : 'my_roadtrip.html';
}

function attachPersonalNotesToDownload(mapId, selector = 'a[href="/download_current_map"]') {
  document.addEventListener('click', async (event) => {
    const link = event.target.closest && event.target.closest(selector);
    // Leave ctrl/cmd/shift/middle clicks to the browser.
    if (!link || event.defaultPrevented || event.button !== 0 ||
        event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    if (link.dataset.busy) return;
    link.dataset.busy = '1';
    const label = link.textContent;
    link.textContent = 'Preparing download…';
    try {
      const response = await fetch(link.href, { credentials: 'same-origin' });
      if (!response.ok || response.redirected) throw new Error('download failed');
      let personal = null;
      try { personal = localStorage.getItem('personalText_' + mapId); } catch (_) { /* storage blocked */ }
      const html = withPersonalNotes(await response.text(), personal);
      const url = URL.createObjectURL(new Blob([html], { type: 'text/html' }));
      const save = document.createElement('a');
      save.href = url;
      save.download = downloadName(response);
      document.body.append(save);
      save.click();
      save.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (_) {
      // Fall back to the plain server download, which also shows any sign-in or
      // access error page.
      window.location.href = link.href;
    } finally {
      link.textContent = label;
      delete link.dataset.busy;
    }
  });
}
