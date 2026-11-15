/* Searchable hierarchical folder model for the local visual archive.
   No filesystem calls; only indexed folder paths already present in export.json. */
(function () {
  "use strict";

  function normalize(input) {
    let value = String(input || "").replace(/\\/g, "/");
    if (value.startsWith("//")) {
      value = "//" + value.slice(2).replace(/\/+/g, "/");
    } else {
      value = value.replace(/\/+/g, "/");
    }
    if (value === "/") return value;
    if (/^[A-Za-z]:\/$/.test(value)) return value;
    return value.replace(/\/+$/g, "");
  }

  function ancestors(input) {
    const path = normalize(input);
    if (!path) return [];
    let prefix, segments;
    if (path.startsWith("//")) {
      const parts = path.slice(2).split("/").filter(Boolean);
      if (parts.length < 2) return [{path, name: path, depth: 0}];
      prefix = "//" + parts.slice(0, 2).join("/");
      segments = parts.slice(2);
    } else if (/^[A-Za-z]:\//.test(path)) {
      prefix = path.slice(0, 3);
      segments = path.slice(3).split("/").filter(Boolean);
    } else if (path.startsWith("/")) {
      prefix = "/";
      segments = path.slice(1).split("/").filter(Boolean);
    } else {
      const parts = path.split("/").filter(Boolean);
      prefix = parts.shift() || "";
      segments = parts;
    }
    const result = [{path: prefix, name: prefix, depth: 0}];
    for (const segment of segments) {
      prefix = prefix.endsWith("/") ? prefix + segment : prefix + "/" + segment;
      result.push({path: prefix, name: segment, depth: result.length});
    }
    return result;
  }

  function isWithin(path, parent) {
    let child = normalize(path), root = normalize(parent);
    if (!child || !root) return false;
    if (/^[A-Za-z]:/.test(root) && /^[A-Za-z]:/.test(child)) {
      child = child.toLowerCase();
      root = root.toLowerCase();
    }
    return child === root || child.startsWith(root.endsWith("/") ? root : root + "/");
  }

  function matches(path, includes, excludes) {
    for (const excluded of excludes) {
      if (isWithin(path, excluded)) return false;
    }
    if (!includes.size) return true;
    for (const included of includes) {
      if (isWithin(path, included)) return true;
    }
    return false;
  }

  function build(decks) {
    const nodes = new Map();
    const roots = [];
    for (const deck of decks) {
      const chain = ancestors(deck.folder_path);
      for (const entry of chain) {
        if (nodes.has(entry.path)) continue;
        const parentPath = entry.depth ? chain[entry.depth - 1].path : null;
        const node = {
          ...entry, parentPath, children: [],
          directDecks: 0, directSnippets: 0, decks: 0, snippets: 0,
        };
        nodes.set(entry.path, node);
        if (parentPath === null) roots.push(node);
        else nodes.get(parentPath).children.push(node);
      }
      if (chain.length) {
        const leaf = nodes.get(chain[chain.length - 1].path);
        leaf.directDecks += 1;
        leaf.directSnippets += Number(deck.slide_count) || 0;
      }
    }

    // Parents are created before children. Aggregate bottom-up once.
    for (const node of [...nodes.values()].reverse()) {
      node.decks += node.directDecks;
      node.snippets += node.directSnippets;
      if (node.parentPath !== null) {
        const parent = nodes.get(node.parentPath);
        parent.decks += node.decks;
        parent.snippets += node.snippets;
      }
    }
    const sortNodes = list => {
      list.sort((a, b) => a.name.localeCompare(b.name, undefined, {sensitivity: "base"}));
      for (const node of list) sortNodes(node.children);
    };
    sortNodes(roots);
    return {nodes, roots};
  }

  function defaultExpanded(tree) {
    const selected = new Set();
    for (const root of tree.roots) {
      let current = root;
      for (let level = 0; level < 7 && current && current.children.length === 1; level++) {
        selected.add(current.path);
        current = current.children[0];
      }
    }
    return selected;
  }

  function visible(tree, expanded, query, limit = 360) {
    const value = String(query || "").trim().replace(/\\/g, "/").toLowerCase();
    let allowed = null;
    if (value) {
      allowed = new Set();
      for (const node of tree.nodes.values()) {
        if (!node.path.toLowerCase().includes(value)) continue;
        let ancestor = node;
        while (ancestor && !allowed.has(ancestor.path)) {
          allowed.add(ancestor.path);
          ancestor = ancestor.parentPath === null ? null : tree.nodes.get(ancestor.parentPath);
        }
      }
    }
    const rows = [];
    let hidden = 0;
    function traverse(items) {
      for (const node of items) {
        if (allowed && !allowed.has(node.path)) continue;
        if (rows.length >= limit) { hidden++; continue; }
        const open = Boolean(value) || expanded.has(node.path);
        rows.push({node, open});
        if (open && node.children.length) traverse(node.children);
      }
    }
    traverse(tree.roots);
    return {rows, truncated: hidden > 0, totalMatches: allowed ? allowed.size : tree.nodes.size};
  }

  const api = {normalize, ancestors, isWithin, matches, build, defaultExpanded, visible};
  if (typeof window !== "undefined") window.FolderFilterTree = api;
  if (typeof module !== "undefined" && module.exports) module.exports = api;
})();
