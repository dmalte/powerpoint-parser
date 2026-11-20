/* Incremental, loopback-only index updates; no full archive JSON reload. */
(function () {
  "use strict";

  function merge(data, page) {
    if (!page || !Number.isSafeInteger(page.cursor) || page.cursor < 0 ||
        !Array.isArray(page.upserts) || !Array.isArray(page.removed) ||
        !page.stats || !Number.isSafeInteger(page.stats.deck_count) ||
        !Number.isSafeInteger(page.stats.slide_count)) {
      throw new Error("Invalid live index response");
    }
    const current = Number.isSafeInteger(data.live_cursor) ? data.live_cursor : 0;
    if (page.cursor < current) {
      throw new Error("Out-of-order live index response");
    }
    const ids = new Set(page.removed);
    for (const item of page.upserts) {
      if (!item || !item.deck || typeof item.deck.id !== "string" ||
          !Array.isArray(item.slides) || item.slides.some(s => s.deck_id !== item.deck.id)) {
        throw new Error("Invalid live deck update");
      }
      ids.add(item.deck.id);
    }
    const changed = ids.size > 0;
    if (changed) {
      data.decks = data.decks.filter(deck => !ids.has(deck.id));
      data.slides = data.slides.filter(slide => !ids.has(slide.deck_id));
      for (const item of page.upserts) {
        data.decks.push(item.deck);
        data.slides.push(...item.slides);
      }
      const byDay = new Map();
      for (const deck of data.decks) {
        const date = deck.modified_date;
        if (!date) continue;
        const item = byDay.get(date) || {date, deck_count: 0, slide_count: 0};
        item.deck_count += 1;
        item.slide_count += Number(deck.slide_count) || 0;
        byDay.set(date, item);
      }
      data.daily = Array.from(byDay.values()).sort((a, b) => a.date.localeCompare(b.date));
      data.stats.folder_count = new Set(data.decks.map(d => d.folder_path)).size;
    }
    data.live_cursor = page.cursor;
    data.stats.deck_count = page.stats.deck_count;
    data.stats.slide_count = page.stats.slide_count;
    return {changed, removed: page.removed, upserts: page.upserts, has_more: !!page.has_more};
  }

  const api = {merge};
  if (typeof window !== "undefined") window.LiveIndex = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
