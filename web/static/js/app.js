/* PowerPoint Visual Archive Viewer — Client-side application */
(function () {
  "use strict";

  /* ═══════════════ STATE ═══════════════ */
  let DATA = { decks: [], slides: [], daily: [], folders: [], stats: {} };
  let deckMap = {};          // deck_id -> deck
  let filteredSlides = [];   // currently visible slides
  let currentModalIdx = -1;  // index in filteredSlides
  let starredSlides = loadStarredSlides();
  let heatmapWindow = loadHeatmapWindow();
  const GRID_PAGE_SIZE = 240;
  const perf = window.PPTViewerPerf;
  let gridPage = 0;

  const filters = {
    search: "",
    searchTerms: [],     // committed search tags (Enter to add)
    deckId: null,
    folder: null,
    fileType: "all",       // "all", "pptx", "pdf"
    dateRange: null,       // {from, to} ISO strings
    quickFilter: "all",
    starredOnly: false,
    searchScopes: {
      deck: true,
      folder: true,
      title: true,
      subtitle: true,
      body: true,
      extra: true,
      notes: true,
    },
  };

  /* ═══════════════ INIT ═══════════════ */
  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const requestStart = perf.now();
      const resp = await fetch("data/export.json", { cache: "no-store" });
      perf.end("data.fetch_headers_ms", requestStart);
      if (!resp.ok) throw new Error("Failed to load data/export.json");
      const bodyStart = perf.now();
      const raw = await resp.text();
      perf.end("data.body_read_ms", bodyStart);
      const declaredSize = resp.headers.get("Content-Length");
      perf.setExportBytes(declaredSize !== null ? Number(declaredSize) : new Blob([raw]).size);
      const parseStart = perf.now();
      DATA = JSON.parse(raw);
      perf.end("data.json_parse_ms", parseStart);
      perf.setLibrary(DATA.decks.length, DATA.slides.length);
    } catch (e) {
      document.getElementById("slide-grid").innerHTML =
        '<p style="padding:20px;color:#c00;">Could not load data. Run <code>pptviewer build</code> first, then open via <code>pptviewer serve</code>.</p>';
      console.error(e);
      return;
    }

    // Build lookup and cache derived fields used by filtering/rendering.
    const normalizeStart = perf.now();
    DATA.decks.forEach(d => { deckMap[d.id] = d; });
    normalizeData();
    perf.end("data.normalize_ms", normalizeStart);

    const initialUiStart = perf.now();
    renderDashboard();
    renderQuickFilterYears();
    renderFolderList();
    renderDeckList();
    initHeatmapWindowControl();
    renderHeatmap();
    applyFilters();
    bindEvents();
    perf.end("startup.initial_ui_ms", initialUiStart);
    // From browser navigation start to the first fully built grid (excludes image fetches).
    perf.record("startup.interactive_ms", perf.now());
    perf.refreshPanel();
  });

  /* ═══════════════ EVENTS ═══════════════ */
  function bindEvents() {
    // Search
    const searchInput = document.getElementById("search-input");
    let debounce;
    searchInput.addEventListener("input", () => {
      clearTimeout(debounce);
      debounce = setTimeout(() => {
        filters.search = searchInput.value.trim().toLowerCase();
        applyFilters();
      }, 200);
    });
    searchInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        clearTimeout(debounce);
        const term = searchInput.value.trim();
        if (term) {
          filters.searchTerms.push(term);
          filters.search = "";
          searchInput.value = "";
          applyFilters();
        }
      }
    });

    document.querySelectorAll("#search-scopes input[type='checkbox']").forEach(box => {
      box.addEventListener("change", () => {
        filters.searchScopes[box.dataset.scope] = box.checked;
        applyFilters();
      });
    });

    // Deck search
    const deckSearch = document.getElementById("deck-search");
    deckSearch.addEventListener("input", () => {
      renderDeckList(deckSearch.value.trim().toLowerCase());
    });

    // Quick filter buttons (event delegation for dynamic year buttons)
    document.getElementById("quick-filters").addEventListener("click", (e) => {
      const btn = e.target.closest(".filter-btn[data-filter]");
      if (!btn) return;
      document.querySelectorAll("#quick-filters .filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      filters.quickFilter = btn.dataset.filter;
      filters.dateRange = quickFilterToDateRange(filters.quickFilter);
      applyFilters();
    });
    document.getElementById("starred-toggle").addEventListener("click", () => {
      filters.starredOnly = !filters.starredOnly;
      document.getElementById("starred-toggle").classList.toggle("active", filters.starredOnly);
      applyFilters();
    });

    // File type filter
    document.getElementById("filetype-filters").addEventListener("click", (e) => {
      const btn = e.target.closest(".filter-btn[data-filetype]");
      if (!btn) return;
      document.querySelectorAll("#filetype-filters .filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      filters.fileType = btn.dataset.filetype;
      applyFilters();
    });

    // Sort / Group
    document.getElementById("sort-select").addEventListener("change", applyFilters);
    document.getElementById("group-select").addEventListener("change", applyFilters);
    document.getElementById("deck-break-toggle").addEventListener("change", applyFilters);
    document.getElementById("page-prev").addEventListener("click", () => changeGridPage(-1));
    document.getElementById("page-next").addEventListener("click", () => changeGridPage(1));

    const heatmapWindowSelect = document.getElementById("heatmap-window-select");
    if (heatmapWindowSelect) {
      heatmapWindowSelect.addEventListener("change", () => {
        heatmapWindow = heatmapWindowSelect.value;
        saveHeatmapWindow();
        renderHeatmap();
      });
    }

    // Modal
    document.getElementById("modal-close").addEventListener("click", closeModal);
    document.getElementById("modal-overlay").addEventListener("click", e => {
      if (e.target === e.currentTarget) closeModal();
    });
    document.getElementById("modal-prev").addEventListener("click", () => navigateModal(-1));
    document.getElementById("modal-next").addEventListener("click", () => navigateModal(1));
    document.addEventListener("keydown", e => {
      if (document.getElementById("modal-overlay").classList.contains("hidden")) return;
      if (e.key === "Escape") closeModal();
      if (e.key === "ArrowLeft") navigateModal(-1);
      if (e.key === "ArrowRight") navigateModal(1);
    });

    // Open actions
    document.getElementById("btn-open-file").addEventListener("click", () => {
      const slide = filteredSlides[currentModalIdx];
      if (!slide) return;
      const deck = deckMap[slide.deck_id];
      if (deck) openPath(deck.file_path, "file");
    });
    document.getElementById("btn-copy-path").addEventListener("click", () => {
      const slide = filteredSlides[currentModalIdx];
      if (!slide) return;
      const deck = deckMap[slide.deck_id];
      if (deck) {
        navigator.clipboard.writeText(deck.file_path).then(() => {
          const btn = document.getElementById("btn-copy-path");
          btn.textContent = "Copied!";
          setTimeout(() => { btn.textContent = "Copy Path"; }, 1500);
        });
      }
    });
    document.getElementById("btn-open-folder").addEventListener("click", () => {
      const slide = filteredSlides[currentModalIdx];
      if (!slide) return;
      const deck = deckMap[slide.deck_id];
      if (deck) openPath(deck.file_path, "folder");
    });
    document.getElementById("btn-toggle-star").addEventListener("click", () => {
      const slide = filteredSlides[currentModalIdx];
      if (!slide) return;
      toggleStar(slide.id);
    });
  }

  /* ═══════════════ FILTERING ═══════════════ */
  function normalizeData() {
    DATA.decks.forEach(deck => {
      const name = deck.file_name || "";
      deck._fileType = name.includes(".") ? name.split(".").pop().toLowerCase() : "";
      deck._searchDeck = name.toLowerCase();
      deck._searchFolder = (deck.folder_path || "").toLowerCase();
    });

    DATA.slides.forEach((slide, sourceIndex) => {
      const deck = deckMap[slide.deck_id];
      slide._sourceIndex = sourceIndex;
      slide._searchFields = {
        deck: deck?._searchDeck || "",
        folder: deck?._searchFolder || "",
        title: (slide.title || "").toLowerCase(),
        subtitle: (slide.subtitle || "").toLowerCase(),
        body: (slide.body || "").toLowerCase(),
        extra: (slide.extra || "").toLowerCase(),
        notes: (slide.notes || "").toLowerCase(),
      };
      slide._searchCacheKey = "";
      slide._searchBlob = "";
    });
  }

  function activeSearchScopeKey() {
    return Object.entries(filters.searchScopes)
      .filter(([, enabled]) => enabled)
      .map(([scope]) => scope)
      .join("|");
  }

  function searchBlob(slide, scopeKey) {
    if (slide._searchCacheKey !== scopeKey) {
      const fields = slide._searchFields || {};
      slide._searchBlob = scopeKey.split("|").filter(Boolean).map(scope => fields[scope] || "").join(" ");
      slide._searchCacheKey = scopeKey;
    }
    return slide._searchBlob;
  }

  function applyFilters() {
    const interactionStart = perf.now();
    const q = filters.search;
    const committedTerms = filters.searchTerms;
    const hasSearch = q || committedTerms.length > 0;
    const range = filters.dateRange;
    const scopeKey = hasSearch ? activeSearchScopeKey() : "";

    filteredSlides = DATA.slides.filter(s => {
      const deck = deckMap[s.deck_id];
      if (!deck) return false;

      // Deck / folder filter
      if (filters.deckId && s.deck_id !== filters.deckId) return false;
      if (filters.folder && deck.folder_path !== filters.folder) return false;
      if (filters.starredOnly && !isStarred(s.id)) return false;

      // File type filter (derived once during normalization)
      if (filters.fileType !== "all" && deck._fileType !== filters.fileType) return false;

      // Date range
      if (range) {
        const d = deck.modified_date;
        if (d < range.from || d > range.to) return false;
      }

      // Text search — cached per active search-scope combination.
      if (hasSearch) {
        const blob = searchBlob(s, scopeKey);

        // Each committed term must match (AND between tags)
        for (const term of committedTerms) {
          if (!matchesSearch(term.toLowerCase(), blob)) return false;
        }
        // Live input must also match if present
        if (q && !matchesSearch(q, blob)) return false;
      }

      return true;
    });

    perf.end(hasSearch ? "interaction.search_filter_ms" : "interaction.filter_ms", interactionStart);
    // Sort
    const sortStart = perf.now();
    const sortVal = document.getElementById("sort-select").value;
    sortSlides(filteredSlides, sortVal);
    perf.end("interaction.sort_ms", sortStart);
    filteredSlides.forEach((slide, index) => { slide._filteredIndex = index; });

    gridPage = 0;
    renderActiveFilters();
    renderGrid(filteredSlides);
    document.getElementById("result-count").textContent =
      `${filteredSlides.length} slide${filteredSlides.length !== 1 ? "s" : ""}`;
    perf.end("interaction.filter_to_grid_ms", interactionStart);
  }

  function sortSlides(arr, mode) {
    arr.sort((a, b) => {
      const da = deckMap[a.deck_id], db = deckMap[b.deck_id];
      switch (mode) {
        case "starred": {
          const starDelta = Number(isStarred(b.id)) - Number(isStarred(a.id));
          if (starDelta !== 0) return starDelta;
          return (db?.modified_time || 0) - (da?.modified_time || 0) || a.num - b.num;
        }
        case "date-desc": return (db?.modified_time || 0) - (da?.modified_time || 0) || a.num - b.num;
        case "date-asc":  return (da?.modified_time || 0) - (db?.modified_time || 0) || a.num - b.num;
        case "name-asc":  return (da?.file_name || "").localeCompare(db?.file_name || "") || a.num - b.num;
        case "slide-num": return a.num - b.num;
        default: return 0;
      }
    });
  }

  function quickFilterToDateRange(key) {
    const now = new Date();
    const today = isoDate(now);
    switch (key) {
      case "today": return { from: today, to: today };
      case "week": {
        const d = new Date(now);
        d.setDate(d.getDate() - d.getDay());
        return { from: isoDate(d), to: today };
      }
      case "month": {
        const d = new Date(now.getFullYear(), now.getMonth(), 1);
        return { from: isoDate(d), to: today };
      }
      case "year": {
        const d = new Date(now.getFullYear(), 0, 1);
        return { from: isoDate(d), to: today };
      }
      default:
        if (key && key.startsWith("year:")) {
          const y = key.slice(5);
          return { from: `${y}-01-01`, to: `${y}-12-31` };
        }
        return null;
    }
  }

  function renderQuickFilterYears() {
    const container = document.getElementById("quick-filters");
    if (!container) return;
    const years = new Set();
    DATA.decks.forEach(d => {
      if (d.modified_date) years.add(d.modified_date.slice(0, 4));
    });
    const currentYear = String(new Date().getFullYear());
    Array.from(years).filter(Boolean).sort((a, b) => Number(b) - Number(a)).forEach(year => {
      if (year === currentYear) return; // already covered by "This Year"
      const btn = document.createElement("button");
      btn.className = "filter-btn";
      btn.dataset.filter = `year:${year}`;
      btn.textContent = year;
      container.appendChild(btn);
    });
  }

  /* ═══════════════ RENDERING ═══════════════ */

  /* ── Dashboard ── */
  function renderDashboard() {
    setText("dash-total-decks", ".dash-number", DATA.stats.deck_count || 0);
    setText("dash-total-slides", ".dash-number", DATA.stats.slide_count || 0);

    // Count decks changed this week
    const now = new Date();
    const weekAgo = new Date(now); weekAgo.setDate(weekAgo.getDate() - 7);
    const weekStr = isoDate(weekAgo);
    const recentCount = DATA.decks.filter(d => d.modified_date >= weekStr).length;
    setText("dash-recent", ".dash-number", recentCount);
  }

  function initHeatmapWindowControl() {
    const select = document.getElementById("heatmap-window-select");
    if (!select) return;

    const options = getHeatmapWindowOptions();
    if (options.length === 0) {
      select.innerHTML = '<option value="rolling-12m">Last 12 months</option>';
      heatmapWindow = "rolling-12m";
      return;
    }

    if (!options.some(option => option.value === heatmapWindow)) {
      heatmapWindow = options[0].value;
      saveHeatmapWindow();
    }

    select.innerHTML = options
      .map(option => `<option value="${option.value}">${escHtml(option.label)}</option>`)
      .join("");
    select.value = heatmapWindow;
  }

  function getHeatmapWindowOptions() {
    const years = new Set();
    DATA.daily.forEach(item => {
      if (item.date) years.add(item.date.slice(0, 4));
    });
    DATA.decks.forEach(deck => {
      if (deck.modified_date) years.add(deck.modified_date.slice(0, 4));
    });

    const orderedYears = Array.from(years)
      .filter(Boolean)
      .sort((a, b) => Number(b) - Number(a));

    return [
      { value: "rolling-12m", label: "Last 12 months" },
      ...orderedYears.map(year => ({ value: `year:${year}`, label: year })),
    ];
  }

  function setText(parentId, selector, val) {
    const el = document.getElementById(parentId);
    if (el) {
      const child = el.querySelector(selector);
      if (child) child.textContent = val;
    }
  }

  /* ── Folder list ── */
  function renderFolderList() {
    const ul = document.getElementById("folder-list");
    ul.innerHTML = "";
    DATA.folders.forEach(f => {
      const li = document.createElement("li");
      li.textContent = f.split(/[\\/]/).pop() || f;
      li.title = f;
      li.addEventListener("click", () => {
        filters.folder = filters.folder === f ? null : f;
        filters.deckId = null;
        highlightActive(ul, li, filters.folder === f);
        clearDeckHighlight();
        applyFilters();
      });
      ul.appendChild(li);
    });
  }

  /* ── Deck list ── */
  function renderDeckList(filterText) {
    const ul = document.getElementById("deck-list");
    ul.innerHTML = "";
    DATA.decks
      .filter(d => !filterText || d.file_name.toLowerCase().includes(filterText))
      .forEach(d => {
        const li = document.createElement("li");
        li.textContent = d.file_name;
        li.title = `${d.file_path}\n${d.slide_count} slides · ${formatDate(d.modified_date)}`;
        if (filters.deckId === d.id) li.classList.add("active");
        li.addEventListener("click", () => {
          filters.deckId = filters.deckId === d.id ? null : d.id;
          filters.folder = null;
          clearFolderHighlight();
          highlightActive(ul, li, filters.deckId === d.id);
          applyFilters();
        });
        ul.appendChild(li);
      });
  }

  /* ── Active filter tags ── */
  function renderActiveFilters() {
    const container = document.getElementById("active-filters");
    container.innerHTML = "";
    if (filters.deckId) addFilterTag(container, "Deck: " + (deckMap[filters.deckId]?.file_name || filters.deckId), () => { filters.deckId = null; clearDeckHighlight(); applyFilters(); });
    if (filters.folder) addFilterTag(container, "Folder: " + filters.folder.split(/[\\/]/).pop(), () => { filters.folder = null; clearFolderHighlight(); applyFilters(); });
    if (filters.fileType !== "all") addFilterTag(container, "Type: ." + filters.fileType, () => { filters.fileType = "all"; document.querySelectorAll("#filetype-filters .filter-btn").forEach(b => b.classList.toggle("active", b.dataset.filetype === "all")); applyFilters(); });
    filters.searchTerms.forEach((term, idx) => {
      addFilterTag(container, `Search: "${term}"`, () => {
        filters.searchTerms.splice(idx, 1);
        applyFilters();
      });
    });
    if (filters.search) addFilterTag(container, `Search: "${filters.search}"`, () => { filters.search = ""; document.getElementById("search-input").value = ""; applyFilters(); });
    if (filters.starredOnly) addFilterTag(container, "Starred only", () => { filters.starredOnly = false; document.getElementById("starred-toggle").classList.remove("active"); applyFilters(); });
    if (filters.dateRange && filters.quickFilter === "all") {
      addFilterTag(container, `Date: ${filters.dateRange.from} → ${filters.dateRange.to}`, () => { filters.dateRange = null; applyFilters(); });
    }
  }

  function addFilterTag(container, text, onRemove) {
    const span = document.createElement("span");
    span.className = "filter-tag";
    span.innerHTML = `${escHtml(text)} <button class="remove">&times;</button>`;
    span.querySelector(".remove").addEventListener("click", onRemove);
    container.appendChild(span);
  }

  /* ── Slide grid ── */
  function renderGrid(slides) {
    const gridStart = perf.now();
    const container = document.getElementById("slide-grid");
    const totalPages = Math.max(1, Math.ceil(slides.length / GRID_PAGE_SIZE));
    gridPage = Math.max(0, Math.min(gridPage, totalPages - 1));
    const pageStart = gridPage * GRID_PAGE_SIZE;
    const pageSlides = slides.slice(pageStart, pageStart + GRID_PAGE_SIZE);

    const groupMode = document.getElementById("group-select").value;
    const deckBreak = document.getElementById("deck-break-toggle").checked;
    const groups = groupSlides(pageSlides, groupMode);
    const fragment = document.createDocumentFragment();

    groups.forEach(group => {
      if (group.label) {
        const header = document.createElement("div");
        header.className = "group-header";
        header.textContent = group.label;
        fragment.appendChild(header);
      }
      let prevDeckId = null;
      group.items.forEach(slide => {
        if (deckBreak && groupMode === "none" && prevDeckId !== null && slide.deck_id !== prevDeckId) {
          const brk = document.createElement("div");
          brk.className = "deck-break";
          fragment.appendChild(brk);
        }
        prevDeckId = slide.deck_id;
        fragment.appendChild(createSlideCard(slide, slide._filteredIndex));
      });
    });

    container.replaceChildren(fragment);
    renderPagination(slides.length, pageStart, pageSlides.length, totalPages);
    perf.end("grid.render_ms", gridStart);
  }

  function renderPagination(total, pageStart, visibleCount, totalPages) {
    const first = total === 0 ? 0 : pageStart + 1;
    const last = pageStart + visibleCount;
    document.getElementById("result-range").textContent = total ? `Showing ${first}–${last}` : "No results";
    document.getElementById("page-indicator").textContent = `Page ${gridPage + 1} of ${totalPages}`;
    document.getElementById("page-prev").disabled = gridPage === 0;
    document.getElementById("page-next").disabled = gridPage >= totalPages - 1 || total === 0;
  }

  function changeGridPage(delta) {
    const totalPages = Math.max(1, Math.ceil(filteredSlides.length / GRID_PAGE_SIZE));
    const nextPage = Math.max(0, Math.min(gridPage + delta, totalPages - 1));
    if (nextPage === gridPage) return;
    gridPage = nextPage;
    renderGrid(filteredSlides);
    document.getElementById("content").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function createSlideCard(slide, globalIdx) {
    const deck = deckMap[slide.deck_id];
    const card = document.createElement("div");
    card.className = "slide-card";
    if (isStarred(slide.id)) card.classList.add("slide-card-starred");
    card.addEventListener("click", () => openModal(globalIdx));

    const actions = document.createElement("div");
    actions.className = "slide-card-actions";

    const starBtn = document.createElement("button");
    starBtn.className = `icon-btn ${isStarred(slide.id) ? "icon-btn-starred" : ""}`;
    starBtn.type = "button";
    starBtn.title = isStarred(slide.id) ? "Remove star" : "Add star";
    starBtn.innerHTML = isStarred(slide.id) ? "★" : "☆";
    starBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleStar(slide.id);
    });

    const openBtn = document.createElement("button");
    openBtn.className = "icon-btn";
    openBtn.type = "button";
    openBtn.title = "Open original presentation";
    openBtn.innerHTML = "↗";
    openBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      const deck = deckMap[slide.deck_id];
      if (deck) openPath(deck.file_path, "file");
    });

    actions.appendChild(starBtn);
    actions.appendChild(openBtn);

    const img = document.createElement("img");
    img.addEventListener("load", () => {
      if (img._perfStart !== undefined) perf.end("image.thumbnail_ms", img._perfStart);
    }, { once: true });
    img.addEventListener("error", () => {
      perf.count("image.thumbnail_errors");
    }, { once: true });
    img.dataset.src = slide.thumb;
    img.alt = slide.title || `Slide ${slide.num}`;
    img.loading = "lazy";
    // Lazy load via IntersectionObserver
    lazyObserver.observe(img);

    const info = document.createElement("div");
    info.className = "slide-card-info";

    const title = document.createElement("div");
    title.className = "slide-card-title";
    title.textContent = slide.title || `Slide ${slide.num}`;

    const sub = document.createElement("div");
    sub.className = "slide-card-sub";
    sub.textContent = deck ? `${deck.file_name} · ${formatDate(deck.modified_date)}` : "";

    const snippet = document.createElement("div");
    snippet.className = "slide-card-snippet";
    snippet.textContent = slide.subtitle || slide.body || slide.extra || slide.text || "No extracted text";

    info.appendChild(title);
    info.appendChild(sub);
    info.appendChild(snippet);
    card.appendChild(actions);
    card.appendChild(img);
    card.appendChild(info);
    return card;
  }

  function groupSlides(slides, mode) {
    if (mode === "none") return [{ label: null, items: slides }];

    const map = new Map();
    slides.forEach(s => {
      let key;
      const deck = deckMap[s.deck_id];
      switch (mode) {
        case "deck": key = s.deck_id; break;
        case "day":  key = deck?.modified_date || "Unknown"; break;
        case "week": key = getWeekLabel(deck?.modified_date); break;
        default: key = "All";
      }
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(s);
    });

    return Array.from(map.entries()).map(([key, items]) => {
      let label;
      switch (mode) {
        case "deck": label = deckMap[key]?.file_name || key; break;
        case "day":  label = formatDate(key); break;
        case "week": label = key; break;
        default: label = key;
      }
      return { label, items };
    });
  }

  /* ═══════════════ HEATMAP ═══════════════ */
  function renderHeatmap() {
    const container = document.getElementById("heatmap-container");
    if (!DATA.daily || DATA.daily.length === 0) {
      container.innerHTML = '<p style="color:#888;font-size:.85rem;">No activity data yet.</p>';
      return;
    }

    // Build date → count map
    const countMap = {};
    DATA.daily.forEach(d => {
      countMap[d.date] = d.slide_count || d.deck_count || 0;
    });

    const windowSpec = getHeatmapWindowSpec(heatmapWindow);
    const cells = buildHeatmapCells(windowSpec, countMap);
    const maxCount = cells.reduce((max, cell) => {
      if (!cell.inRange) return max;
      return Math.max(max, cell.count);
    }, 0);

    const cellSize = 13, gap = 2, totalSize = cellSize + gap;
    const weeks = Math.ceil(cells.length / 7);
    const svgW = weeks * totalSize + 30;
    const svgH = 7 * totalSize + 20;

    const colors = ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"];

    let svg = `<svg width="${svgW}" height="${svgH}" xmlns="http://www.w3.org/2000/svg">`;

    // Month labels
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    let lastMonthKey = null;
    cells.forEach((c, i) => {
      if (!c.inRange) return;
      const col = Math.floor(i / 7);
      const date = parseIsoDate(c.date);
      const monthKey = `${date.getFullYear()}-${date.getMonth()}`;
      if (monthKey !== lastMonthKey) {
        lastMonthKey = monthKey;
        svg += `<text x="${col * totalSize + 30}" y="10" class="heatmap-label">${months[date.getMonth()]}</text>`;
      }
    });

    // Cells
    cells.forEach((c, i) => {
      const col = Math.floor(i / 7);
      const row = c.day;
      const x = col * totalSize + 30;
      const y = row * totalSize + 16;
      const lvl = !c.inRange || maxCount === 0 ? 0 : Math.min(4, Math.ceil((c.count / maxCount) * 4));
      const color = c.inRange ? colors[lvl] : "#f7f8fa";
      const cellClass = c.inRange ? "heatmap-cell" : "heatmap-cell heatmap-cell-outside";
      const title = c.inRange ? `${c.date}: ${c.count} slides` : `${c.date}: outside selected window`;
      svg += `<rect class="${cellClass}" data-date="${c.date}" data-count="${c.count}" data-active="${c.inRange ? "true" : "false"}" ` +
             `x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="${color}">` +
             `<title>${title}</title></rect>`;
    });

    svg += "</svg>";
    container.innerHTML = svg;

    // Click day → filter
    container.querySelectorAll('.heatmap-cell[data-active="true"]').forEach(el => {
      el.addEventListener("click", () => {
        const date = el.dataset.date;
        filters.dateRange = { from: date, to: date };
        filters.quickFilter = "all";
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        applyFilters();
      });
    });
  }

  function getHeatmapWindowSpec(windowValue) {
    if (windowValue && windowValue.startsWith("year:")) {
      const year = Number(windowValue.slice(5));
      return {
        start: new Date(year, 0, 1),
        end: new Date(year, 11, 31),
      };
    }

    const end = todayLocal();
    const start = new Date(end);
    start.setDate(start.getDate() - 364);
    return { start, end };
  }

  function buildHeatmapCells(windowSpec, countMap) {
    const gridStart = startOfWeek(windowSpec.start);
    const gridEnd = endOfWeek(windowSpec.end);
    const cells = [];

    for (let cursor = new Date(gridStart); cursor <= gridEnd; cursor.setDate(cursor.getDate() + 1)) {
      const day = new Date(cursor);
      const iso = isoDate(day);
      const inRange = day >= windowSpec.start && day <= windowSpec.end;
      cells.push({
        date: iso,
        count: inRange ? (countMap[iso] || 0) : 0,
        day: day.getDay(),
        inRange,
      });
    }

    return cells;
  }

  /* ═══════════════ MODAL ═══════════════ */
  function openModal(idx) {
    const modalStart = perf.now();
    currentModalIdx = idx;
    const slide = filteredSlides[idx];
    if (!slide) return;
    const deck = deckMap[slide.deck_id];

    const overlay = document.getElementById("modal-overlay");

    const preview = document.getElementById("modal-image");
    const previewStart = perf.now();
    preview.onload = () => perf.end("image.preview_ms", previewStart);
    preview.onerror = () => perf.count("image.preview_errors");
    preview.src = slide.preview || slide.thumb || "";
    document.getElementById("modal-title").textContent = slide.title || `Slide ${slide.num}`;
    document.getElementById("modal-deck").textContent = deck?.file_name || "";
    document.getElementById("modal-slide-num").textContent = `${slide.num} of ${deck?.slide_count || "?"}`;
    document.getElementById("modal-folder").textContent = deck?.folder_path || "";
    document.getElementById("modal-date").textContent = deck ? formatDate(deck.modified_date) : "";
    document.getElementById("modal-size").textContent = deck ? formatSize(deck.file_size) : "";
    document.getElementById("modal-star-state").textContent = isStarred(slide.id) ? "Yes" : "No";
    document.getElementById("btn-toggle-star").textContent = isStarred(slide.id) ? "Unstar" : "Star";

    const subtitleSection = document.getElementById("modal-subtitle-section");
    const subtitleEl = document.getElementById("modal-subtitle");
    if (slide.subtitle) { subtitleEl.textContent = slide.subtitle; subtitleSection.style.display = ""; }
    else { subtitleSection.style.display = "none"; }

    const textSection = document.getElementById("modal-text-section");
    const textEl = document.getElementById("modal-text");
    if (slide.body) { textEl.textContent = slide.body; textSection.style.display = ""; }
    else { textSection.style.display = "none"; }

    const extraSection = document.getElementById("modal-extra-section");
    const extraEl = document.getElementById("modal-extra");
    if (slide.extra) { extraEl.textContent = slide.extra; extraSection.style.display = ""; }
    else { extraSection.style.display = "none"; }

    const notesSection = document.getElementById("modal-notes-section");
    const notesEl = document.getElementById("modal-notes");
    if (slide.notes) { notesEl.textContent = slide.notes; notesSection.style.display = ""; }
    else { notesSection.style.display = "none"; }

    overlay.classList.remove("hidden");
    perf.end("modal.open_ms", modalStart);
  }

  function closeModal() {
    document.getElementById("modal-overlay").classList.add("hidden");
    currentModalIdx = -1;
  }

  function navigateModal(dir) {
    const next = currentModalIdx + dir;
    if (next >= 0 && next < filteredSlides.length) openModal(next);
  }

  /* ═══════════════ LAZY LOAD ═══════════════ */
  const lazyObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        if (img.dataset.src) {
          img._perfStart = perf.now();
          img.src = img.dataset.src;
          img.removeAttribute("data-src");
        }
        lazyObserver.unobserve(img);
      }
    });
  }, { rootMargin: "200px" });

  /* ═══════════════ SEARCH PARSER ═══════════════ */

  /**
   * Parse a search query into an array of terms.
   * - Quoted strings ("word1 word2") become exact phrase terms.
   * - Unquoted words separated by spaces are individual terms (implicit AND).
   * - The literal word AND between terms is ignored (it's the default).
   * - All terms must match (AND logic).
   *
   * Examples:
   *   'budget'              → ['budget']
   *   'budget report'       → ['budget', 'report']
   *   '"budget report"'     → ['budget report']
   *   '"Q1 results" AND budget' → ['q1 results', 'budget']
   */
  function parseSearchQuery(query) {
    const terms = [];
    const re = /"([^"]+)"|(\S+)/g;
    let match;
    while ((match = re.exec(query)) !== null) {
      const term = (match[1] || match[2]).toLowerCase();
      if (term === "and") continue; // skip explicit AND keyword
      if (term) terms.push(term);
    }
    return terms;
  }

  /**
   * Returns true when ALL parsed search terms are found in the haystack.
   */
  function matchesSearch(query, haystack) {
    const terms = parseSearchQuery(query);
    if (terms.length === 0) return true;
    return terms.every(term => haystack.includes(term));
  }

  /* ═══════════════ HELPERS ═══════════════ */
  function isoDate(d) {
    if (typeof d === "string") return d;
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    return `${year}-${month}-${day}`;
  }

  function parseIsoDate(iso) {
    const [year, month, day] = (iso || "").split("-").map(Number);
    return new Date(year, (month || 1) - 1, day || 1);
  }

  function todayLocal() {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), now.getDate());
  }

  function startOfWeek(date) {
    const start = new Date(date.getFullYear(), date.getMonth(), date.getDate());
    start.setDate(start.getDate() - start.getDay());
    return start;
  }

  function endOfWeek(date) {
    const end = startOfWeek(date);
    end.setDate(end.getDate() + 6);
    return end;
  }

  function formatDate(iso) {
    if (!iso) return "";
    const d = new Date(iso + "T00:00:00");
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function formatSize(bytes) {
    if (!bytes) return "";
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
  }

  function getWeekLabel(dateStr) {
    if (!dateStr) return "Unknown";
    const d = new Date(dateStr + "T00:00:00");
    const start = new Date(d);
    start.setDate(start.getDate() - start.getDay());
    return `Week of ${formatDate(isoDate(start))}`;
  }

  function escHtml(s) {
    const div = document.createElement("div");
    div.textContent = s;
    return div.innerHTML;
  }

  function highlightActive(ul, activeLi, isActive) {
    ul.querySelectorAll("li").forEach(li => li.classList.remove("active"));
    if (isActive) activeLi.classList.add("active");
  }

  function clearDeckHighlight() {
    document.getElementById("deck-list").querySelectorAll("li").forEach(li => li.classList.remove("active"));
  }

  function clearFolderHighlight() {
    document.getElementById("folder-list").querySelectorAll("li").forEach(li => li.classList.remove("active"));
  }

  async function openPath(targetPath, kind) {
    if (!targetPath) return;

    if (window.location.protocol.startsWith("http")) {
      try {
        const response = await fetch(kind === "folder" ? "/api/open-folder" : "/api/open-file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: targetPath }),
        });
        if (response.ok) return;
      } catch (error) {
        console.warn("Server-backed open failed; falling back to file://", error);
      }
    }

    const normalized = targetPath.replace(/\\/g, "/");
    window.open(`file:///${normalized}`);
  }

  function loadStarredSlides() {
    try {
      const raw = window.localStorage.getItem("ppt-visual-archive-stars-v1");
      return raw ? JSON.parse(raw) : {};
    } catch (error) {
      console.warn("Could not read starred slides from localStorage", error);
      return {};
    }
  }

  function saveStarredSlides() {
    try {
      window.localStorage.setItem("ppt-visual-archive-stars-v1", JSON.stringify(starredSlides));
    } catch (error) {
      console.warn("Could not persist starred slides", error);
    }
  }

  function isStarred(slideId) {
    return Boolean(starredSlides[slideId]);
  }

  function toggleStar(slideId) {
    if (isStarred(slideId)) delete starredSlides[slideId];
    else starredSlides[slideId] = Date.now();
    saveStarredSlides();
    applyFilters();
    if (currentModalIdx >= 0) {
      const nextIndex = filteredSlides.findIndex(slide => slide.id === slideId);
      if (nextIndex >= 0) openModal(nextIndex);
      else closeModal();
    }
  }

  function loadHeatmapWindow() {
    try {
      return window.localStorage.getItem("ppt-visual-archive-heatmap-window-v1") || "rolling-12m";
    } catch (error) {
      console.warn("Could not read heatmap window from localStorage", error);
      return "rolling-12m";
    }
  }

  function saveHeatmapWindow() {
    try {
      window.localStorage.setItem("ppt-visual-archive-heatmap-window-v1", heatmapWindow);
    } catch (error) {
      console.warn("Could not persist heatmap window", error);
    }
  }
})();
