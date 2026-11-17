/**
 * Dependency-free Chromium/Edge CDP runner for the synthetic archive benchmark.
 * Requires Node >=22 for its built-in WebSocket. Starts only a loopback server.
 */
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { extname, join, resolve, sep } from 'node:path';

const [browserCommand, siteDirectory, repetitionsRaw, deadlineRaw, sidebarFlag] = process.argv.slice(2);
const verifySidebar = sidebarFlag === '--verify-sidebar';
const profileMemory = sidebarFlag === '--profile-memory';
if (sidebarFlag && !verifySidebar && !profileMemory) throw new Error('Unsupported browser verification mode');
const repetitions = Number(repetitionsRaw || 5);
const deadline = Number(deadlineRaw || 90) * 1000;
if (!browserCommand || !siteDirectory || !Number.isInteger(repetitions) || repetitions < 1) {
  throw new Error('Usage: node measure_viewer.mjs <browser> <site-directory> <repetitions> <timeout-seconds>');
}
if (typeof WebSocket === 'undefined') {
  throw new Error('Node 22+ is required for the built-in WebSocket client');
}

const root = resolve(siteDirectory);
const mime = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.json': 'application/json',
  '.jpg': 'image/jpeg', '.png': 'image/png',
};
const httpServer = createServer(async (request, response) => {
  const route = new URL(request.url || '/', 'http://127.0.0.1').pathname;
  let relative;
  try { relative = decodeURIComponent(route); }
  catch (_) { response.writeHead(400).end(); return; }
  const absolute = resolve(root, '.' + (relative === '/' ? '/index.html' : relative));
  if (!absolute.startsWith(root + sep)) { response.writeHead(403).end(); return; }
  try {
    const data = await readFile(absolute);
    response.setHeader('Content-Type', mime[extname(absolute)] || 'application/octet-stream');
    response.setHeader('Cache-Control', 'no-store');
    response.end(data);
  } catch (_) {
    response.writeHead(404).end('not found');
  }
});
const listen = () => new Promise(resolveReady => {
  httpServer.listen(0, '127.0.0.1', () => resolveReady(httpServer.address().port));
});
const pause = (ms) => new Promise(resolveReady => setTimeout(resolveReady, ms));
const profileDir = await mkdtemp(join(tmpdir(), 'pptviewer-cdp-'));
let browser;
let ws;
let messageId = 0;
const pending = new Map();
const exceptions = [];

function send(method, params = {}) {
  return new Promise((done, fail) => {
    const id = ++messageId;
    pending.set(id, {done, fail});
    ws.send(JSON.stringify({id, method, params}));
  });
}

async function evaluate(expression) {
  const data = await send('Runtime.evaluate', {
    expression, returnByValue: true, awaitPromise: true,
  });
  if (data.exceptionDetails) {
    throw new Error('Browser expression failed: ' + data.exceptionDetails.text);
  }
  return data.result?.value;
}

async function waitUntil(predicate, timeoutMs, label) {
  const begin = Date.now();
  while (Date.now() - begin < timeoutMs) {
    const result = await predicate();
    if (result) return result;
    await pause(100);
  }
  throw new Error('Timed out: ' + label);
}

async function connect(webSocketUrl) {
  ws = new WebSocket(webSocketUrl);
  ws.addEventListener('message', (event) => {
    const packet = JSON.parse(String(event.data));
    if (packet.id && pending.has(packet.id)) {
      const call = pending.get(packet.id);
      pending.delete(packet.id);
      if (packet.error) call.fail(new Error(packet.error.message));
      else call.done(packet.result || {});
    } else if (packet.method === 'Runtime.exceptionThrown') {
      const detail = packet.params?.exceptionDetails;
      exceptions.push(detail?.exception?.description || detail?.text || 'Browser runtime exception');
    }
  });
  await new Promise((done, fail) => {
    ws.addEventListener('open', done, {once: true});
    ws.addEventListener('error', () => fail(new Error('Could not connect to browser CDP')), {once: true});
  });
}

async function browserExperiment() {
  const port = await listen();
  const targetUrl = 'http://127.0.0.1:' + port + '/';
  browser = spawn(browserCommand, [
    '--headless=new', '--no-first-run', '--no-default-browser-check',
    '--disable-dev-shm-usage', '--remote-allow-origins=*',
    '--remote-debugging-port=0', '--user-data-dir=' + profileDir,
    ...(process.platform === 'linux' ? ['--no-sandbox'] : []),
    targetUrl,
  ], {stdio: 'ignore'});
  let browserFailed;
  browser.on('error', (error) => { browserFailed = error; });
  const devtoolsPortFile = join(profileDir, 'DevToolsActivePort');
  const debugPort = await waitUntil(async () => {
    if (browserFailed) throw browserFailed;
    if (browser.exitCode !== null) throw new Error('Browser exited before CDP was ready');
    try { return Number((await readFile(devtoolsPortFile, 'utf8')).split('\n')[0]); }
    catch (_) { return null; }
  }, 20000, 'browser debugger port');

  const target = await waitUntil(async () => {
    const response = await fetch('http://127.0.0.1:' + debugPort + '/json/list');
    const targets = await response.json();
    return targets.find(item => item.type === 'page' && item.webSocketDebuggerUrl);
  }, 12000, 'browser tab');
  await connect(target.webSocketDebuggerUrl);
  await send('Runtime.enable');
  await send('Performance.enable');
  const browserVersion = (await send('Browser.getVersion')).product || 'unknown';
  await waitUntil(() => evaluate('Boolean(window.PPTViewerPerf?.report().timings["startup.interactive_ms"])'), deadline, 'viewer initialized');
  const startingCards = await evaluate('document.querySelectorAll(".slide-card").length');
  const startingDeckRows = await evaluate('document.querySelectorAll("#deck-list li").length');
  const expectedSlides = await evaluate('window.PPTViewerPerf.report().library.slides');
  if (startingCards > 240) throw new Error('Rendered too many cards: ' + startingCards);

  // Optional research-only retained-heap probe (no source paths or content).
  // Force GC before capturing the initial heap and after the normal scripted
  // interactions. Both candidate and baseline get the exact same workload.
  const heapUsedMB = async () => {
    await send('HeapProfiler.collectGarbage');
    const metrics = (await send('Performance.getMetrics')).metrics || [];
    const size = metrics.find(item => item.name === 'JSHeapUsedSize')?.value;
    return size == null ? null : Math.round(size / 1048576 * 100) / 100;
  };
  const initialRetainedHeapMB = profileMemory ? await heapUsedMB() : null;

  // Dispatch the same input/change/click events as a user, not private app functions.
  const searches = ['benchmark', 'Slide 1', 'not-in-the-archive', 'Slide 2', 'benchmark x'];
  for (let i = 0; i < repetitions; i++) {
    const query = searches[i % searches.length];
    await evaluate(`(() => {
      const input = document.getElementById('search-input');
      input.value = ${JSON.stringify(query)};
      input.dispatchEvent(new Event('input', {bubbles:true}));
    })()`);
    await pause(270); // app's normal 200 ms search debounce + execution
  }
  // Clear search to exercise full-library sorting and next-page navigation.
  await evaluate(`(() => {
    const input = document.getElementById('search-input');
    input.value = ''; input.dispatchEvent(new Event('input', {bubbles:true}));
  })()`);
  await pause(300);
  for (const choice of ['name-asc', 'slide-num', 'date-asc', 'date-desc']) {
    await evaluate(`(() => {
      const select = document.getElementById('sort-select');
      select.value = ${JSON.stringify(choice)};
      select.dispatchEvent(new Event('change', {bubbles:true}));
    })()`);
  }
  await evaluate(`(() => {
    document.getElementById('group-select').value = 'deck';
    document.getElementById('group-select').dispatchEvent(new Event('change', {bubbles:true}));
    document.getElementById('page-next').click();
    document.getElementById('content').scrollTop = 900;
  })()`);
  await pause(350);
  await evaluate(`(() => {
    const card = document.querySelector('.slide-card');
    if (card) { card.click(); document.getElementById('modal-close').click(); }
  })()`);

  const report = await evaluate('window.PPTViewerPerf.report()');
  const cards = await evaluate('document.querySelectorAll(".slide-card").length');
  const deckRows = await evaluate('document.querySelectorAll("#deck-list li").length');
  const liveDomNodes = await evaluate('document.getElementsByTagName("*").length');
  const cdpm = (await send('Performance.getMetrics')).metrics || [];
  const cdpMetrics = Object.fromEntries(
    cdpm.filter(metric => ['JSHeapUsedSize', 'Nodes', 'LayoutCount', 'RecalcStyleCount'].includes(metric.name))
      .map(metric => [metric.name, metric.value])
  );
  const postSearchRetainedHeapMB = profileMemory ? await heapUsedMB() : null;
  if (cards > 240) throw new Error('Grid limit violated after interactions: ' + cards);
  if (exceptions.length) throw new Error(exceptions.slice(0, 3).join('; '));
  if (!report.timings['interaction.search_filter_ms']) {
    throw new Error('Search instrumentation produced no measurements');
  }

  // A separate, synthetic-only UI acceptance run is performed *after* the
  // timing/heap snapshot, so the normal measurements stay comparable. Real
  // archives are never searched by document name as part of this benchmark.
  let sidebarVerification = null;
  if (verifySidebar) {
    const decks = report.library.decks;
    const finalName = `deck-${decks - 1}.pptx`;
    sidebarVerification = await evaluate(`(() => {
      const list = document.getElementById('deck-list');
      const prev = document.getElementById('deck-page-prev');
      const next = document.getElementById('deck-page-next');
      const input = document.getElementById('deck-search');
      const firstCount = list.children.length;
      if (!prev.disabled || firstCount > 100) return {passed:false, reason:'initial bound'};
      if (${decks} > 100) {
        next.click();
        if (list.children.length > 100 || prev.disabled) return {passed:false, reason:'next page'};
        prev.click();
        if (list.children.length !== firstCount) return {passed:false, reason:'previous page'};
      }
      input.value = ${JSON.stringify(finalName)};
      input.dispatchEvent(new Event('input', {bubbles:true}));
      const matches = Array.from(list.querySelectorAll('li'));
      if (matches.length !== 1 || matches[0].textContent !== ${JSON.stringify(finalName)})
        return {passed:false, reason:'off-page filename search'};
      matches[0].click();
      const selected = matches[0].getAttribute('aria-pressed') === 'true';
      const filteredCount = Number.parseInt(document.getElementById('result-count').textContent, 10);
      input.value = '';
      input.dispatchEvent(new Event('input', {bubbles:true}));
      const persisted = Number.parseInt(document.getElementById('result-count').textContent, 10) === filteredCount;
      const tag = document.querySelector('#active-filters .filter-tag .remove');
      if (!tag) return {passed:false, reason:'no selected-deck filter tag'};
      tag.click();
      const cleared = Number.parseInt(document.getElementById('result-count').textContent, 10) === ${expectedSlides};
      input.value = '__unknown_synthetic_deck_name__';
      input.dispatchEvent(new Event('input', {bubbles:true}));
      const empty = list.children.length === 0 && prev.disabled && next.disabled &&
        document.getElementById('deck-page-indicator').textContent === 'Page 0 of 0';
      return {passed: selected && persisted && cleared && empty, initial_rows:firstCount,
        selected, persisted, cleared, empty, pages_checked:${decks} > 100 ? 2 : 1};
    })()`);
    if (!sidebarVerification?.passed) {
      throw new Error('Synthetic sidebar interaction failed: ' + JSON.stringify(sidebarVerification));
    }
  }
  // Run synthetic search-scope behavior after timing capture. These queries
  // refer exclusively to the deterministic generated fixture, never the
  // user's production document text, search history, or filenames.
  let searchScopeVerification = null;
  if (verifySidebar) {
    searchScopeVerification = await evaluate(`(async () => {
      const boxes = [...document.querySelectorAll('#search-scopes input[type=checkbox]')];
      const input = document.getElementById('search-input');
      const count = () => Number.parseInt(document.getElementById('result-count').textContent, 10);
      const run = async (scopes, query) => {
        boxes.forEach(box => {
          const enabled = scopes.includes(box.dataset.scope);
          if (box.checked !== enabled) {
            box.checked = enabled;
            box.dispatchEvent(new Event('change', {bubbles:true}));
          }
        });
        input.value = query;
        input.dispatchEvent(new Event('input', {bubbles:true}));
        await new Promise(done => setTimeout(done, 290));
        return count();
      };
      const all = boxes.map(box => box.dataset.scope);
      const scenarios = [
        {scopes:['body'], query:'benchmark', expected:${expectedSlides}},
        {scopes:['title'], query:'benchmark', expected:0},
        {scopes:['subtitle'], query:'subtitle', expected:${expectedSlides}},
        {scopes:['notes'], query:'benchmark', expected:0},
        {scopes:['extra'], query:'benchmark', expected:0},
        {scopes:['folder'], query:'benchmark', expected:${expectedSlides}},
        {scopes:['deck'], query:'deck-0.pptx', expected:Math.min(30, ${expectedSlides})},
        {scopes:['title'], query:'Slide ${expectedSlides - 1}', expected:1},
        {scopes:['title','body'], query:'"Slide ${expectedSlides - 1} benchmark"', expected:1},
      ];
      let passed = true;
      for (const scenario of scenarios) {
        if (await run(scenario.scopes, scenario.query) !== scenario.expected) {
          passed = false;
          break;
        }
      }
      const restored = await run(all, '') === ${expectedSlides};
      return {passed:passed && restored, tested:scenarios.length, restored};
    })()`);
    if (!searchScopeVerification?.passed) {
      throw new Error('Synthetic search-scope regression failed: ' + JSON.stringify(searchScopeVerification));
    }
  }
  return {
    browser_version: browserVersion,
    library_slides: expectedSlides,
    max_visible_cards: Math.max(startingCards, cards),
    sidebar_rows_initial: startingDeckRows,
    sidebar_rows_final: deckRows,
    live_dom_nodes: liveDomNodes,
    sidebar_verification: sidebarVerification,
    search_scope_verification: searchScopeVerification,
    dom_nodes: cdpMetrics.Nodes ?? null,
    js_heap_used_mb: cdpMetrics.JSHeapUsedSize == null ? null : Math.round(cdpMetrics.JSHeapUsedSize / 1048576 * 100) / 100,
    memory_profile: profileMemory ? {
      initial_retained_heap_mb: initialRetainedHeapMB,
      post_search_retained_heap_mb: postSearchRetainedHeapMB,
    } : null,
    cdp_metrics: cdpMetrics,
    browser_report: report,
    scripted_actions: {searches: repetitions, sort_changes: 4, page_changes: 1, modal_openings: 1},
    limitations: verifySidebar
      ? 'Synthetic extracted text and shared placeholder images; no Office COM rendering or real source-document I/O.'
      : 'Local archive browser workload. This does not measure original-file PowerPoint processing or realistic image decoding throughput.',
  };
}

try {
  const result = await browserExperiment();
  process.stdout.write(JSON.stringify(result) + '\n');
} catch (error) {
  process.stderr.write('Browser benchmark failed: ' + error.stack + '\n');
  process.exitCode = 1;
} finally {
  if (ws && ws.readyState === WebSocket.OPEN) ws.close();
  if (browser && browser.exitCode === null) {
    const browserClosed = new Promise(done => browser.once('close', done));
    browser.kill('SIGTERM');
    await Promise.race([browserClosed, pause(2500)]);
    if (browser.exitCode === null) {
      browser.kill('SIGKILL');
      await Promise.race([browserClosed, pause(2500)]);
    }
  }
  await new Promise(done => httpServer.close(done));
  await rm(profileDir, {recursive:true, force:true, maxRetries:10, retryDelay:150});
}
