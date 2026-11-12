(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const rootsEl = $('scan-roots');
  const messageEl = $('settings-message');

  function rootRow(value = '') {
    const row = document.createElement('div');
    row.className = 'root-row';
    const input = document.createElement('input');
    input.type = 'text';
    input.value = value;
    input.placeholder = 'C:\\Users\\you\\Documents\\Presentations';
    input.className = 'scan-root-input';
    const remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'btn';
    remove.textContent = 'Remove';
    remove.addEventListener('click', () => row.remove());
    row.append(input, remove);
    return row;
  }

  function showMessage(text, kind = '') {
    messageEl.textContent = text;
    messageEl.className = `settings-message ${kind}`.trim();
  }

  async function jsonFetch(url, options = {}) {
    const response = await fetch(url, {
      headers: {'Content-Type': 'application/json'},
      ...options,
    });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
    return payload;
  }

  async function loadSettings() {
    try {
      const settings = await jsonFetch('/api/settings');
      rootsEl.textContent = '';
      (settings.scan_roots || []).forEach((root) => rootsEl.append(rootRow(root)));
      if (!rootsEl.children.length) rootsEl.append(rootRow());
      $('type-pptx').checked = (settings.file_types || []).includes('pptx');
      $('type-pdf').checked = (settings.file_types || []).includes('pdf');
      $('scan-interval').value = settings.scan_interval_seconds ?? 1800;
    } catch (error) {
      showMessage(error.message, 'error');
    }
  }

  async function refreshStatus() {
    try {
      const status = await jsonFetch('/api/status');
      $('agent-status').textContent = status.status || 'unknown';
      const phase = status.progress?.phase || status.status || 'unknown';
      const count = Number.isFinite(status.progress?.completed) ? status.progress.completed : 0;
      const total = Number.isFinite(status.progress?.total) ? '/' + status.progress.total : '';
      $('scan-progress').textContent = (status.status === 'scanning' || status.status === 'starting')
        ? 'Progress: ' + phase + ' (' + count + total + ' files)' : '';
      $('last-refresh').textContent = status.last_refresh ? `Last refresh: ${new Date(status.last_refresh).toLocaleString()}` : 'No completed refresh yet';
      $('last-error').textContent = status.last_error ? `Last error: ${status.last_error}` : '';
    } catch (error) {
      $('agent-status').textContent = 'unavailable';
      $('last-error').textContent = error.message;
    }
  }

  $('add-root').addEventListener('click', () => rootsEl.append(rootRow()));

  $('save-settings').addEventListener('click', async () => {
    const scanRoots = [...document.querySelectorAll('.scan-root-input')].map((el) => el.value.trim()).filter(Boolean);
    const fileTypes = [];
    if ($('type-pptx').checked) fileTypes.push('pptx');
    if ($('type-pdf').checked) fileTypes.push('pdf');
    const interval = Number($('scan-interval').value);
    showMessage('Saving…');
    try {
      await jsonFetch('/api/settings', {method: 'POST', body: JSON.stringify({scan_roots: scanRoots, file_types: fileTypes, scan_interval_seconds: interval})});
      showMessage('Settings saved.', 'ok');
      await refreshStatus();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  $('scan-now').addEventListener('click', async () => {
    try {
      const result = await jsonFetch('/api/scan', {method: 'POST', body: '{}'});
      showMessage(result.started ? 'Scan started.' : 'A scan is already running.', result.started ? 'ok' : 'error');
      await refreshStatus();
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  $('open-logs').addEventListener('click', async () => {
    try {
      await jsonFetch('/api/open-logs', {method: 'POST', body: '{}'});
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  $('restart-agent').addEventListener('click', async () => {
    if (!window.confirm('Restart the local archive agent?')) return;
    try {
      await jsonFetch('/api/shutdown', {method: 'POST', body: JSON.stringify({restart: true})});
      showMessage('Agent restart requested.', 'ok');
    } catch (error) {
      showMessage(error.message, 'error');
    }
  });

  loadSettings();
  refreshStatus();
  window.setInterval(refreshStatus, 3000);
})();
