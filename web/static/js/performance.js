/* In-memory, local-only performance measurements for the visual archive. */
(function () {
  "use strict";

  const MAX_SAMPLES = 200; // bounded memory even during long browsing sessions
  const metrics = new Map();
  const counters = {};
  let library = { decks: 0, slides: 0 };
  let exportBytes = null;
  let scrollUntil = 0;
  let scrollRunning = false;
  let previousFrame = 0;

  function now() {
    return performance.now();
  }

  function record(name, milliseconds) {
    if (!/^[a-z][a-z0-9._-]{0,63}$/.test(name) || !Number.isFinite(milliseconds) || milliseconds < 0) return;
    let metric = metrics.get(name);
    if (!metric) {
      metric = { count: 0, total: 0, min: Infinity, max: 0, samples: [] };
      metrics.set(name, metric);
    }
    metric.count += 1;
    metric.total += milliseconds;
    metric.min = Math.min(metric.min, milliseconds);
    metric.max = Math.max(metric.max, milliseconds);
    if (metric.samples.length >= MAX_SAMPLES) metric.samples.shift();
    metric.samples.push(milliseconds);
  }

  function end(name, start) {
    const elapsed = now() - start;
    record(name, elapsed);
    return elapsed;
  }

  function count(name, amount = 1) {
    if (!/^[a-z][a-z0-9._-]{0,63}$/.test(name) || !Number.isFinite(amount) || amount < 0) return;
    counters[name] = (counters[name] || 0) + amount;
  }

  function rounded(number) {
    return Math.round(number * 100) / 100;
  }

  function percentile(sorted, p) {
    if (!sorted.length) return null;
    return rounded(sorted[Math.ceil(sorted.length * p) - 1]);
  }

  function summary() {
    const result = {};
    for (const [name, metric] of metrics.entries()) {
      const sorted = [...metric.samples].sort((a, b) => a - b);
      result[name] = {
        count: metric.count,
        avg_ms: rounded(metric.total / metric.count),
        min_ms: rounded(metric.min),
        p50_ms: percentile(sorted, 0.5),
        p95_ms: percentile(sorted, 0.95),
        max_ms: rounded(metric.max),
        percentile_window: sorted.length,
      };
    }
    return result;
  }

  function navigationMetrics() {
    const nav = performance.getEntriesByType ? performance.getEntriesByType("navigation")[0] : null;
    if (!nav) return null;
    return {
      dom_content_loaded_ms: rounded(nav.domContentLoadedEventEnd),
      load_event_ms: rounded(nav.loadEventEnd),
      response_ms: rounded(nav.responseEnd - nav.requestStart),
      transfer_bytes: nav.transferSize || null,
    };
  }

  function memoryMetrics() {
    // Non-standard: supported primarily by Chromium; null on Firefox/Safari.
    const mem = performance.memory;
    return mem && Number.isFinite(mem.usedJSHeapSize)
      ? { used_js_heap_mb: rounded(mem.usedJSHeapSize / 1048576),
          heap_limit_mb: rounded(mem.jsHeapSizeLimit / 1048576) }
      : null;
  }

  function makeReport() {
    return {
      schema_version: 1,
      generated_at: new Date().toISOString(),
      browser: {
        user_agent: navigator.userAgent,
        hardware_concurrency: navigator.hardwareConcurrency || null,
        device_memory_gb: navigator.deviceMemory || null,
      },
      library: { ...library, export_json_bytes: exportBytes },
      navigation: navigationMetrics(),
      memory: memoryMetrics(),
      timings: summary(),
      counters: { ...counters },
      notes: [
        "Timings are milliseconds, taken from this browser session only.",
        "p50/p95 use up to the most recent 200 observations per metric.",
        "scroll.frame_gap_ms measures frame gaps during scrolling, not guaranteed FPS.",
        "Browser memory is unavailable on some browsers.",
        "No source paths, filenames, slide text, or search queries are recorded.",
      ],
    };
  }

  function updatePanel() {
    const el = document.getElementById("perf-summary");
    if (!el) return;
    const report = makeReport();
    const rows = Object.entries(report.timings).sort(([a], [b]) => a.localeCompare(b))
      .map(([name, m]) => `${name.padEnd(30)} n=${String(m.count).padStart(4)}  p50=${String(m.p50_ms).padStart(8)}  p95=${String(m.p95_ms).padStart(8)}  max=${String(m.max_ms).padStart(8)} ms`);
    el.textContent = [
      `Library: ${library.decks} decks / ${library.slides} slides`,
      `JSON bytes: ${exportBytes === null ? "unavailable" : exportBytes}`,
      `JS heap: ${report.memory ? report.memory.used_js_heap_mb + " MB" : "unavailable"}`,
      `Counters: ${JSON.stringify(report.counters)}`,
      "",
      ...rows,
      "",
      "Download the JSON for backend scan/build timings and full diagnostics.",
    ].join("\n");
  }

  async function downloadReport() {
    const report = makeReport();
    report.backend_runs = [];
    report.backend_available = false;
    // The endpoint is loopback-only and is queried only after the user clicks Download.
    if (location.protocol === "http:" || location.protocol === "https:") {
      try {
        const response = await fetch("/api/performance", { cache: "no-store" });
        if (response.ok) {
          const result = await response.json();
          if (Array.isArray(result.runs)) {
            report.backend_runs = result.runs;
            report.backend_available = true;
          }
        }
      } catch (_) {
        // Static servers and file:// usage still produce browser-only reports.
      }
    }
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = "pptviewer-performance-" + new Date().toISOString().replace(/[:.]/g, "-") + ".json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  function sampleScrollFrame(ts) {
    if (previousFrame && document.visibilityState !== "hidden") {
      const gap = ts - previousFrame;
      record("scroll.frame_gap_ms", gap);
      if (gap >= 50) count("scroll.frame_gaps_over_50ms");
    }
    previousFrame = ts;
    if (now() < scrollUntil) {
      requestAnimationFrame(sampleScrollFrame);
    } else {
      scrollRunning = false;
      previousFrame = 0;
    }
  }

  function bindDiagnostics() {
    const toggle = document.getElementById("perf-toggle");
    const panel = document.getElementById("perf-panel");
    if (toggle && panel) {
      toggle.addEventListener("click", () => {
        const opening = panel.classList.contains("hidden");
        panel.classList.toggle("hidden", !opening);
        toggle.setAttribute("aria-expanded", String(opening));
        if (opening) updatePanel();
      });
      document.getElementById("perf-refresh").addEventListener("click", updatePanel);
      document.getElementById("perf-clear").addEventListener("click", () => {
        metrics.clear();
        Object.keys(counters).forEach(name => { delete counters[name]; });
        updatePanel();
      });
      document.getElementById("perf-download").addEventListener("click", async () => {
        const button = document.getElementById("perf-download");
        button.disabled = true;
        try { await downloadReport(); }
        finally { button.disabled = false; }
      });
    }
    const content = document.getElementById("content");
    if (content) {
      content.addEventListener("scroll", () => {
        scrollUntil = now() + 200;
        if (!scrollRunning && document.visibilityState !== "hidden") {
          scrollRunning = true;
          requestAnimationFrame(sampleScrollFrame);
        }
      }, { passive: true });
    }
  }

  if (typeof PerformanceObserver !== "undefined" &&
      PerformanceObserver.supportedEntryTypes &&
      PerformanceObserver.supportedEntryTypes.includes("longtask")) {
    try {
      new PerformanceObserver(list => {
        for (const entry of list.getEntries()) record("main_thread.longtask_ms", entry.duration);
      }).observe({ entryTypes: ["longtask"] });
    } catch (_) { /* Not supported in this browser. */ }
  }

  document.addEventListener("DOMContentLoaded", bindDiagnostics);
  window.PPTViewerPerf = Object.freeze({
    now, record, end, count,
    setLibrary(decks, slides) {
      library = { decks: Number(decks) || 0, slides: Number(slides) || 0 };
    },
    setExportBytes(bytes) {
      if (Number.isFinite(bytes) && bytes >= 0) exportBytes = bytes;
    },
    report: makeReport,
    refreshPanel: updatePanel,
  });
}());
