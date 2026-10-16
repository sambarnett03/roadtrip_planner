function attachDriveControls(map, stops, context) {
  const viewKey = 'driveMapView_' + context.owner_id + '_' + context.map_id;
  try {
    const saved = JSON.parse(sessionStorage.getItem(viewKey));
    sessionStorage.removeItem(viewKey);
    if (saved && Array.isArray(saved.center) && saved.center.length === 2 &&
        saved.center.every(Number.isFinite) && Number.isFinite(saved.zoom)) {
      map.setView(saved.center, saved.zoom, { animate: false });
    }
  } catch (_) { /* Map controls also work when browser storage is unavailable. */ }

  let saving = false;
  for (const stop of stops) {
    const marker = stop.marker;
    let closeTimer;
    let pinned = false;
    const cancelClose = () => clearTimeout(closeTimer);
    const scheduleClose = () => {
      cancelClose();
      closeTimer = setTimeout(() => {
        const popup = marker.getPopup().getElement();
        if (!pinned && !saving && popup && !popup.matches(':hover') &&
            !popup.contains(document.activeElement)) marker.closePopup();
      }, 350);
    };
    marker.on('mouseover', () => {
      cancelClose();
      marker.openPopup();
    });
    marker.on('mouseout', scheduleClose);
    // Clicking/tapping pins the panel open, including for keyboard and touch users.
    marker.on('click', () => { pinned = true; marker.openPopup(); });
    marker.on('popupclose', () => { pinned = false; cancelClose(); });
    marker.on('popupopen', () => {
      const popup = marker.getPopup().getElement();
      popup.onmouseenter = cancelClose;
      popup.onmouseleave = scheduleClose;
      popup.onfocusout = scheduleClose;
      if (!stop.doc_id || popup.querySelector('.drive-control')) return;

      const control = document.createElement('div');
      control.className = 'drive-control';
      control.style.cssText = 'border-top:1px solid #ddd;margin-top:12px;padding-top:10px';
      const label = document.createElement('label');
      label.style.cssText = 'display:flex;align-items:center;gap:8px;cursor:pointer';
      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.checked = stop.included;
      const offline = window.location.protocol === 'file:';
      checkbox.disabled = !context.can_edit || offline;
      label.append(checkbox, document.createTextNode('Include in drive'));
      const status = document.createElement('div');
      status.setAttribute('role', 'status');
      status.style.cssText = 'font-size:12px;margin-top:6px;max-width:250px';
      if (offline) status.textContent = 'Open this map online to change the drive.';
      else if (!context.can_edit) status.textContent = 'Only the owner and editors can change the drive.';
      control.append(label, status);
      // Leaflet's popup.update() rebuilds .leaflet-popup-content from the popup's
      // content element, so add the control inside that element to keep it.
      const content = marker.getPopup().getContent?.();
      const host = content && typeof content.append === 'function'
        ? content : popup.querySelector('.leaflet-popup-content');
      host.append(control);
      L.DomEvent.disableClickPropagation(control);

      checkbox.addEventListener('change', async () => {
        if (saving) { checkbox.checked = stop.included; return; }
        const included = checkbox.checked;
        saving = true;
        pinned = true;
        checkbox.disabled = true;
        status.textContent = 'Saving…';
        try {
          const response = await fetch('/api/stops/update', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...context, doc_id: stop.doc_id,
                                   field: 'drive', value: included ? 'y' : 'n' })
          });
          if (response.redirected) throw new Error('Please sign in again, then retry.');
          const data = await response.json();
          if (!response.ok) throw new Error(data.error || 'Could not update the drive.');
          stop.included = included;
          status.textContent = 'Saved. Updating route…';
          try {
            const center = map.getCenter();
            sessionStorage.setItem(viewKey, JSON.stringify({ center: [center.lat, center.lng],
                                                            zoom: map.getZoom() }));
          } catch (_) { /* A successful save must not depend on browser storage. */ }
          window.location.reload();
        } catch (error) {
          checkbox.checked = stop.included;
          status.textContent = error.message || 'Could not update the drive. Please try again.';
        } finally {
          saving = false;
          checkbox.disabled = false;
        }
      });
      marker.getPopup().update();
    });
  }
}
