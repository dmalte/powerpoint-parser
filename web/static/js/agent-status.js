/* Loopback-only agent progress and pause/resume controls. Static viewers remain usable. */
(() => {
  'use strict';
  const indicator = document.getElementById('agent-progress');
  const pauseButton = document.getElementById('agent-pause');
  const resumeButton = document.getElementById('agent-resume');
  if (!indicator || !pauseButton || !resumeButton || location.protocol === 'file:') return;

  let busy = false;
  let actionBusy = false;
  let seenActiveScan = false;

  async function refresh() {
    if (busy || document.visibilityState === 'hidden') return;
    busy = true;
    try {
      const response = await fetch('/api/status', {cache: 'no-store'});
      if (response.status === 503 || response.status === 404) {
        clearInterval(interval);
        indicator.hidden = true;
        pauseButton.hidden = true;
        resumeButton.hidden = true;
        return;
      }
      if (!response.ok) return;
      const data = await response.json();
      const paused = !!data.scan_paused;
      const transitioning = data.status === 'pausing' || !!data.snapshot_pending;
      const phase = data.progress?.phase || data.status || 'scanning';
      const complete = Number.isFinite(data.progress?.completed) ? data.progress.completed : 0;
      const total = Number.isFinite(data.progress?.total) ? '/' + data.progress.total : '';
      pauseButton.hidden = paused;
      pauseButton.disabled = actionBusy || transitioning;
      resumeButton.hidden = !paused;
      resumeButton.disabled = actionBusy || transitioning;

      if (transitioning) {
        seenActiveScan = true;
        indicator.textContent = 'Pausing and saving: ' + phase + ' (' + complete + total + ' files)';
        indicator.hidden = false;
      } else if (data.status === 'scanning' || data.status === 'starting') {
        seenActiveScan = true;
        indicator.textContent = 'Indexing: ' + phase + ' (' + complete + total + ' files)';
        indicator.hidden = false;
      } else if (data.status === 'paused') {
        indicator.textContent = 'Scan paused — partial archive saved (reload to browse latest)';
        indicator.hidden = false;
        seenActiveScan = false;
      } else if (data.status === 'error') {
        indicator.textContent = 'Archive operation failed — see Settings';
        indicator.hidden = false;
      } else if (data.status === 'idle' && seenActiveScan) {
        indicator.textContent = data.last_summary?.viewer_rebuilt === false
          ? 'Archive checked — no changes'
          : 'Archive updated — reload for new results';
        indicator.hidden = false;
        seenActiveScan = false;
      }
    } catch (_) {
      // Non-agent web servers may not implement these endpoints.
    } finally {
      busy = false;
    }
  }

  async function changeScanState(route) {
    if (actionBusy) return;
    actionBusy = true;
    pauseButton.disabled = true;
    resumeButton.disabled = true;
    try {
      const response = await fetch(route, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: '{}',
      });
      if (!response.ok) throw new Error('Scan control failed (' + response.status + ')');
      indicator.hidden = false;
      indicator.textContent = route === '/api/pause'
        ? 'Pause requested — finishing current document and saving archive…'
        : 'Resuming incremental scan…';
    } catch (error) {
      indicator.hidden = false;
      indicator.textContent = error.message + ' — check Settings';
    } finally {
      actionBusy = false;
      await refresh();
    }
  }

  pauseButton.addEventListener('click', () => changeScanState('/api/pause'));
  resumeButton.addEventListener('click', () => changeScanState('/api/resume'));
  const interval = setInterval(refresh, 3000);
  refresh();
})();
