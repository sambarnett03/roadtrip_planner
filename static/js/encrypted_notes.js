// Embedded into generated maps so personal notes still work in downloaded HTML.
function createEncryptedNotes({ auth, docRef, editableDiv, toggle, ownerId, mapId }) {
  const status = document.createElement('div');
  status.style.cssText = 'margin:0 20px 12px;font:12px Arial,sans-serif;white-space:pre-wrap';
  status.setAttribute('role', 'status');
  editableDiv.after(status);
  const retry = document.createElement('button');
  retry.textContent = 'Retry';
  retry.hidden = true;
  status.after(retry);

  let unsubscribe = null;
  let generation = 0;
  let revision = null;
  let dirty = false;
  let saving = false;
  let refreshing = false;
  let refreshAgain = false;
  let blocked = false;
  let timer = null;
  let edits = 0;

  function lock() {
    editableDiv.contentEditable = 'false';
    editableDiv.oninput = null;
  }

  function stop() {
    generation++;
    clearTimeout(timer);
    if (unsubscribe) unsubscribe();
    unsubscribe = null;
    lock();
  }

  async function api(method, body) {
    const user = auth.currentUser;
    if (!user) throw new Error('Please sign in to access shared notes.');
    const token = await user.getIdToken();
    const query = new URLSearchParams({ owner_id: ownerId, map_id: mapId });
    const response = await fetch('/api/notes?' + query, {
      method,
      credentials: 'omit',
      cache: 'no-store',
      headers: { Authorization: 'Bearer ' + token, 'Content-Type': 'application/json' },
      ...(body ? { body: JSON.stringify({ ...body, owner_id: ownerId, map_id: mapId }) } : {})
    });
    const data = await response.json();
    if (!response.ok) {
      const error = new Error(data.error || 'Could not load or save notes.');
      error.status = response.status;
      throw error;
    }
    return data;
  }

  async function refresh() {
    if (!toggle.checked || !auth.currentUser || dirty || saving) return;
    if (refreshing) {
      refreshAgain = true;
      return;
    }
    refreshing = true;
    const currentGeneration = generation;
    const currentEdits = edits;
    try {
      const data = await api('GET');
      if (currentGeneration !== generation || currentEdits !== edits || dirty || saving) return;
      // Do not replace unchanged HTML: that would move the cursor during live updates.
      if (revision !== data.revision) editableDiv.innerHTML = data.text;
      revision = data.revision;
      blocked = false;
      editableDiv.contentEditable = data.can_edit ? 'true' : 'false';
      editableDiv.oninput = data.can_edit ? () => {
        dirty = true;
        edits++;
        status.textContent = 'Unsaved changes';
        clearTimeout(timer);
        timer = setTimeout(save, 700);
      } : null;
      status.textContent = data.can_edit ? 'Saved' : 'You have read access to these notes.';
      retry.hidden = true;
    } catch (error) {
      if (currentGeneration !== generation || currentEdits !== edits || dirty || saving) return;
      lock();
      status.textContent = error.message;
      retry.hidden = false;
    } finally {
      refreshing = false;
      if (refreshAgain) {
        refreshAgain = false;
        refresh();
      }
    }
  }

  async function save() {
    if (!dirty || saving || blocked || !toggle.checked) return;
    saving = true;
    const currentEdits = edits;
    status.textContent = 'Saving…';
    try {
      const data = await api('POST', { text: editableDiv.innerHTML, revision });
      revision = data.revision;
      dirty = edits !== currentEdits;
      status.textContent = dirty ? 'Unsaved changes' : 'Saved';
      retry.hidden = true;
      if (dirty) timer = setTimeout(save, 700);
    } catch (error) {
      // Keep the user's edits on screen. A conflict requires copying edits and reloading.
      blocked = error.status === 409 || error.status === 503 || error.status === 403;
      if (blocked) lock();
      status.textContent = error.message + '\nYour unsaved edits are still shown above.';
      retry.hidden = blocked;
    } finally {
      saving = false;
      if (!dirty) refresh();
    }
  }

  function loadShared() {
    if (dirty || saving) return;
    stop();
    revision = null;
    status.textContent = 'Loading shared notes…';
    retry.hidden = true;
    editableDiv.innerHTML = '';
    if (!auth.currentUser) {
      status.textContent = 'Verifying access…';
      return;
    }
    refresh();
    // Firestore remains the live notification channel; plaintext is only read via Flask.
    unsubscribe = docRef.onSnapshot(() => refresh(), () => {
      status.textContent = 'Live updates unavailable. Retry to reconnect.';
      retry.hidden = false;
    });
  }

  function loadPersonal() {
    if (dirty || saving) {
      toggle.checked = true;
      localStorage.setItem('noteMode', 'shared');
      status.textContent += '\nSave or copy your edits before switching notes.';
      return;
    }
    stop();
    status.textContent = '';
    retry.hidden = true;
    editableDiv.innerHTML = localStorage.getItem('personalText_' + mapId) || '';
    editableDiv.contentEditable = 'true';
    editableDiv.oninput = () => {
      localStorage.setItem('personalText_' + mapId, editableDiv.innerHTML);
    };
  }

  retry.onclick = () => {
    if (dirty) save();
    else loadShared();
  };
  auth.onAuthStateChanged(() => {
    if (!toggle.checked) return;
    if (dirty || saving) {
      blocked = true;
      stop();
      status.textContent = 'Sign-in changed. Copy your unsaved edits, then reload.';
    } else {
      loadShared();
    }
  });
  window.addEventListener('beforeunload', (event) => {
    if (dirty || saving) {
      event.preventDefault();
      event.returnValue = '';
    }
  });
  return { loadShared, loadPersonal };
}
