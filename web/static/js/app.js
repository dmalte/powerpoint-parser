/* PowerPoint Visual Archive Viewer — Client-side application */
(function () {
  "use strict";

  /* ═══════════════ STATE ═══════════════ */
  let DATA = { decks: [], slides: [], daily: [], folders: [], stats: {} };
  let deckMap = {};          // deck_id -> deck
  let filteredSlides = [];   // currently visible slides
  let currentModalIdx = -1;  // index in filteredSlides

  const filters = {
    search: "",
    deckId: null,
    folder: null,
    dateRange: null,       // {from, to} ISO strings
    quickFilter: "all",
  };

  /* ═══════════════ INIT ═══════════════ */
  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const resp = await fetch("data/export.json");
      if (!resp.ok) throw new Error("Failed to load data/export.json");
      DATA = await resp.json();
    } catch (e) {
      document.getElementById("slide-grid").innerHTML =
        '<p style="padding:20px;color:#c00;">Could not load data. Run <code>pptviewer build</code> first, then open via <code>pptviewer serve</code>.</p>';
      console.error(e);
      return;
    }

    // Build lookup
    DATA.decks.forEach(d => { deckMap[d.id] = d; });

    renderDashboard();
    renderFolderList();
    renderDeckList();
    renderHeatmap();
    applyFilters();
    bindEvents();
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

    // Deck search
    const deckSearch = document.getElementById("deck-search");
    deckSearch.addEventListener("input", () => {
      renderDeckList(deckSearch.value.trim().toLowerCase());
    });

    // Quick filter buttons
    document.querySelectorAll(".filter-btn[data-filter]").forEach(btn => {
      btn.addEventListener("click", () => {
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        btn.classList.add("active");
        filters.quickFilter = btn.dataset.filter;
        filters.dateRange = quickFilterToDateRange(filters.quickFilter);
        applyFilters();
      });
    });

    // Sort / Group
    document.getElementById("sort-select").addEventListener("change", applyFilters);
    document.getElementById("group-select").addEventListener("change", applyFilters);

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
      if (deck) window.open("file:///" + deck.file_path.replace(/\\/g, "/"));
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
      if (deck) window.open("file:///" + deck.folder_path.replace(/\\/g, "/"));
    });
  }

  /* ═══════════════ FILTERING ═══════════════ */
  function applyFilters() {
    const q = filters.search;
    const range = filters.dateRange;

    filteredSlides = DATA.slides.filter(s => {
      const deck = deckMap[s.deck_id];
      if (!deck) return false;

      // Deck / folder filter
      if (filters.deckId && s.deck_id !== filters.deckId) return false;
      if (filters.folder && deck.folder_path !== filters.folder) return false;

      // Date range
      if (range) {
        const d = deck.modified_date;
        if (d < range.from || d > range.to) return false;
      }

      // Text search
      if (q) {
        const haystack = [
          deck.file_name, deck.folder_path, s.title, s.text
        ].join(" ").toLowerCase();
        if (!haystack.includes(q)) return false;
      }

      return true;
    });

    // Sort
    const sortVal = document.getElementById("sort-select").value;
    sortSlides(filteredSlides, sortVal);

    renderActiveFilters();
    renderGrid(filteredSlides);
    document.getElementById("result-count").textContent =
      `${filteredSlides.length} slide${filteredSlides.length !== 1 ? "s" : ""}`;
  }

  function sortSlides(arr, mode) {
    arr.sort((a, b) => {
      const da = deckMap[a.deck_id], db = deckMap[b.deck_id];
      switch (mode) {
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
      default: return null;
    }
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
    if (filters.search) addFilterTag(container, `Search: "${filters.search}"`, () => { filters.search = ""; document.getElementById("search-input").value = ""; applyFilters(); });
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
    const container = document.getElementById("slide-grid");
    container.innerHTML = "";

    const groupMode = document.getElementById("group-select").value;
    const groups = groupSlides(slides, groupMode);

    groups.forEach(group => {
      if (group.label) {
        const header = document.createElement("div");
        header.className = "group-header";
        header.textContent = group.label;
        container.appendChild(header);
      }
      group.items.forEach((slide, idx) => {
        const globalIdx = slides.indexOf(slide);
        const card = createSlideCard(slide, globalIdx);
        container.appendChild(card);
      });
    });
  }

  function createSlideCard(slide, globalIdx) {
    const deck = deckMap[slide.deck_id];
    const card = document.createElement("div");
    card.className = "slide-card";
    card.addEventListener("click", () => openModal(globalIdx));

    const img = document.createElement("img");
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

    info.appendChild(title);
    info.appendChild(sub);
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
    let maxCount = 0;
    DATA.daily.forEach(d => {
      countMap[d.date] = d.slide_count || d.deck_count || 0;
      if (countMap[d.date] > maxCount) maxCount = countMap[d.date];
    });

    // Generate 52 weeks (364 days) ending today
    const today = new Date();
    const cells = [];
    for (let i = 363; i >= 0; i--) {
      const d = new Date(today);
      d.setDate(d.getDate() - i);
      const iso = isoDate(d);
      cells.push({ date: iso, count: countMap[iso] || 0, day: d.getDay() });
    }

    const cellSize = 13, gap = 2, totalSize = cellSize + gap;
    const weeks = Math.ceil(cells.length / 7);
    const svgW = weeks * totalSize + 30;
    const svgH = 7 * totalSize + 20;

    const colors = ["#ebedf0", "#c6e48b", "#7bc96f", "#239a3b", "#196127"];

    let svg = `<svg width="${svgW}" height="${svgH}" xmlns="http://www.w3.org/2000/svg">`;

    // Month labels
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    let lastMonth = -1;
    cells.forEach((c, i) => {
      const col = Math.floor(i / 7);
      const m = new Date(c.date).getMonth();
      if (m !== lastMonth) {
        lastMonth = m;
        svg += `<text x="${col * totalSize + 30}" y="10" class="heatmap-label">${months[m]}</text>`;
      }
    });

    // Cells
    cells.forEach((c, i) => {
      const col = Math.floor(i / 7);
      const row = c.day;
      const x = col * totalSize + 30;
      const y = row * totalSize + 16;
      const lvl = maxCount === 0 ? 0 : Math.min(4, Math.ceil((c.count / maxCount) * 4));
      const color = colors[lvl];
      svg += `<rect class="heatmap-cell" data-date="${c.date}" data-count="${c.count}" ` +
             `x="${x}" y="${y}" width="${cellSize}" height="${cellSize}" fill="${color}">` +
             `<title>${c.date}: ${c.count} slides</title></rect>`;
    });

    svg += "</svg>";
    container.innerHTML = svg;

    // Click day → filter
    container.querySelectorAll(".heatmap-cell").forEach(el => {
      el.addEventListener("click", () => {
        const date = el.dataset.date;
        filters.dateRange = { from: date, to: date };
        filters.quickFilter = "all";
        document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
        applyFilters();
      });
    });
  }

  /* ═══════════════ MODAL ═══════════════ */
  function openModal(idx) {
    currentModalIdx = idx;
    const slide = filteredSlides[idx];
    if (!slide) return;
    const deck = deckMap[slide.deck_id];

    const overlay = document.getElementById("modal-overlay");

    document.getElementById("modal-image").src = slide.preview || slide.thumb || "";
    document.getElementById("modal-title").textContent = slide.title || `Slide ${slide.num}`;
    document.getElementById("modal-deck").textContent = deck?.file_name || "";
    document.getElementById("modal-slide-num").textContent = `${slide.num} of ${deck?.slide_count || "?"}`;
    document.getElementById("modal-folder").textContent = deck?.folder_path || "";
    document.getElementById("modal-date").textContent = deck ? formatDate(deck.modified_date) : "";
    document.getElementById("modal-size").textContent = deck ? formatSize(deck.file_size) : "";

    const textSection = document.getElementById("modal-text-section");
    const textEl = document.getElementById("modal-text");
    if (slide.text) { textEl.textContent = slide.text; textSection.style.display = ""; }
    else { textSection.style.display = "none"; }

    const notesSection = document.getElementById("modal-notes-section");
    const notesEl = document.getElementById("modal-notes");
    if (slide.notes) { notesEl.textContent = slide.notes; notesSection.style.display = ""; }
    else { notesSection.style.display = "none"; }

    overlay.classList.remove("hidden");
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
          img.src = img.dataset.src;
          img.removeAttribute("data-src");
        }
        lazyObserver.unobserve(img);
      }
    });
  }, { rootMargin: "200px" });

  /* ═══════════════ HELPERS ═══════════════ */
  function isoDate(d) {
    if (typeof d === "string") return d;
    return d.toISOString().slice(0, 10);
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
})();
