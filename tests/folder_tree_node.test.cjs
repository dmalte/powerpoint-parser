"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const folder = require("../web/static/js/folder-tree.js");

test("POSIX and Windows paths use segment-boundary recursive filtering", () => {
  assert.equal(folder.normalize("C:\\Users\\m\\Docs\\"), "C:/Users/m/Docs");
  assert.deepEqual(folder.ancestors("/Users/m/work")[0], {path: "/", name: "/", depth: 0});
  assert(folder.isWithin("/Users/m/work/sub", "/Users/m/work"));
  assert(!folder.isWithin("/Users/m/workshop", "/Users/m/work"));
  assert(folder.isWithin("C:\\Users\\m\\docs\\file", "c:/Users/m/DOCS"));
  assert(!folder.isWithin("D:/data", "C:/data"));
  assert(folder.isWithin("//nas/share/notes", "//nas/share"));
});

test("multiple includes and exclusions compose with recursive path rules", () => {
  const includes = new Set(["/Users/m/work", "/Users/m/personal"]);
  const excludes = new Set(["/Users/m/work/private"]);
  assert(folder.matches("/Users/m/work/projects", includes, excludes));
  assert(folder.matches("/Users/m/personal/notes", includes, excludes));
  assert(!folder.matches("/Users/m/work/private/notes", includes, excludes));
  assert(!folder.matches("/Users/m/workshop", includes, excludes));
  assert(!folder.matches("/Users/m/public", includes, excludes));
  assert(folder.matches("/Users/m/public", new Set(), excludes));
  assert(!folder.matches("/Users/m/work/private", new Set(), excludes));
  assert(!folder.matches("/Users/m/work/private", includes, new Set(["/Users/m/work"])));
});

test("tree aggregates recursively and displays search matches with ancestors", () => {
  const decks = [
    {folder_path:"/Users/m/work",slide_count:2},
    {folder_path:"/Users/m/work/project",slide_count:4},
    {folder_path:"/Users/m/work/project/deep",slide_count:3},
    {folder_path:"/Users/m/workshop",slide_count:1},
    {folder_path:"C:\\Projects\\Docs",slide_count:5},
    {folder_path:"C:\\Projects\\Docs\\Nested",slide_count:7},
  ];
  const tree = folder.build(decks);
  assert.equal(tree.nodes.get("/Users/m/work").decks,3);
  assert.equal(tree.nodes.get("/Users/m/work").snippets,9);
  assert.equal(tree.nodes.get("/Users/m/work").directDecks,1);
  assert.equal(tree.nodes.get("C:/Projects/Docs").decks,2);
  assert.equal(tree.nodes.get("C:/Projects/Docs").snippets,12);
  assert.equal(tree.nodes.get("/Users/m/workshop").decks,1);
  assert.equal(tree.nodes.get("/Users/m/workshop").snippets,1);

  const result = folder.visible(tree,new Set(),"project/deep");
  const paths = result.rows.map(row=>row.node.path);
  assert(paths.includes("/Users/m/work/project/deep"));
  assert(paths.includes("/Users/m/work"));
  assert(!paths.includes("/Users/m/workshop"));
  assert(!paths.includes("C:/Projects/Docs"));
  assert(result.rows.some(row=>row.node.path==="/Users/m/work/project"&&row.open));
});

test("dense trees stay collapsed and rendered entries remain bounded", () => {
  const decks = [];
  for (let i=0;i<18000;i++) {
    decks.push({folder_path:"/Users/m/workspace/" + (i%40) + "/project-" + i,slide_count:i%7+1});
  }
  const tree=folder.build(decks);
  assert(tree.nodes.size>=18000);
  const expanded=folder.defaultExpanded(tree);
  const collapsed=folder.visible(tree,expanded,"",360);
  assert(collapsed.rows.length<360);
  assert.equal(tree.nodes.get("/Users/m/workspace").decks,18000);
  assert.equal(tree.nodes.get("/Users/m/workspace").snippets,decks.reduce((sum,d)=>sum+d.slide_count,0));
  const search=folder.visible(tree,new Set(),"project-",360);
  assert(search.rows.length<=360);
  assert(search.truncated);
});
