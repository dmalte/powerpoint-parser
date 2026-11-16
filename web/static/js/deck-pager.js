/* Bound the presentation list without narrowing which filenames can be searched.
   Only the visible page becomes DOM nodes; the full dataset stays searchable. */
(function () {
  "use strict";

  const PAGE_SIZE = 100;

  function paginate(decks, query = "", requestedPage = 0) {
    const needle = String(query || "").trim().toLowerCase();
    const matches = decks.filter(deck =>
      !needle || (deck._searchDeck ?? String(deck.file_name || "").toLowerCase()).includes(needle)
    );
    const total = matches.length;
    const pages = Math.ceil(total / PAGE_SIZE);
    const requested = Number.isInteger(requestedPage) ? requestedPage : 0;
    const page = pages === 0 ? 0 : Math.max(0, Math.min(requested, pages - 1));
    const start = page * PAGE_SIZE;
    return {entries: matches.slice(start, start + PAGE_SIZE), page, pages, start, total};
  }

  const api = {PAGE_SIZE, paginate};
  if (typeof window !== "undefined") window.DeckPager = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
