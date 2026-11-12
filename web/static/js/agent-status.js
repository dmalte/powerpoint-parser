/* Optional agent progress indicator; static-file and plain-serve modes stay usable. */
(() => {
  'use strict';
  const indicator = document.getElementById('agent-progress');
  if (!indicator || location.protocol === 'file:') return;
  let busy = false;
  let seenActiveScan = false;

  async function refresh() {
    if (busy || document.visibilityState === 'hidden') return;
    busy = true;
    try {
      const response = await fetch('/api/status', { cache: 'no-store' });
      if (response.status === 503 || response.status === 404) {
        // Viewer served without the background agent: stop polling.
        clearInterval(interval);
        indicator.hidden = true;
        return;
      }
      if (!response.ok) return;
      const data = await response.json();
      const phase = data.progress?.phase || 'scanning';
      const complete = Number.isFinite(data.progress?.completed) ? data.progress.completed : 0;
      const total = Number.isFinite(data.progress?.total) ? '/' + data.progress.total : '';
      if (data.status === 'scanning' || data.status === 'starting') {
        seenActiveScan = true;
        indicator.textContent = 'Indexing: ' + phase + ' (' + complete + total + ' files)';
        indicator.hidden = false;
      } else if (data.status === 'error') {
        indicator.textContent = 'Scan failed — see Settings';
        indicator.hidden = false;
      } else if (data.status === 'idle' && seenActiveScan) {
        indicator.textContent = 'Archive updated — reload for new results';
        indicator.hidden = false;
        seenActiveScan = false;
      }
    } catch (_) {
      // Non-agent web servers may not implement this endpoint.
    } finally {
      busy = false;
    }
  }

  const interval = setInterval(refresh, 3000);
  refresh();
})();
