"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const {merge} = require("../web/static/js/live-index.js");

const oldDeck = {id:"a", folder_path:"C:/notes", modified_date:"2026-11-19", slide_count:2};
const oldSlides = [{id:"a-1",deck_id:"a"},{id:"a-2",deck_id:"a"}];
function initial() {return {decks:[{...oldDeck}],slides:oldSlides.map(s=>({...s})),stats:{deck_count:1,slide_count:2,folder_count:1},daily:[],live_cursor:10};}
function updated() {return {cursor:11,stats:{deck_count:1,slide_count:1},has_more:false,removed:[],upserts:[{deck:{...oldDeck,slide_count:1},slides:[{id:"a-new",deck_id:"a"}]}]};}

test("initial incremental data is a complete replacement of one committed deck", () => {
  const data=initial(); const page=updated();
  assert(merge(data,page).changed);
  assert.deepEqual(data.slides.map(s=>s.id),["a-new"]);
  assert.equal(data.decks.length,1);
  assert.equal(data.stats.slide_count,1);
  assert.equal(data.stats.folder_count,1);
  assert.equal(data.live_cursor,11);
  assert.equal(data.daily[0].slide_count,1);
  merge(data,{...page,cursor:12});
  assert.equal(data.decks.length,1);
  assert.equal(data.slides.length,1);
});

test("new deck is appended and tombstone removes old cards without duplicates", () => {
  const data=initial();
  const page={cursor:11,stats:{deck_count:2,slide_count:3},has_more:true,removed:[],upserts:[{deck:{id:"b",folder_path:"C:/other",modified_date:"2026-11-18",slide_count:1},slides:[{id:"b-1",deck_id:"b"}]}]};
  assert(merge(data,page).has_more);
  assert.deepEqual(data.decks.map(d=>d.id),["a","b"]);
  assert.equal(data.slides.length,3);
  assert.equal(data.stats.folder_count,2);
  merge(data,{cursor:12,stats:{deck_count:1,slide_count:1},has_more:false,removed:["a"],upserts:[]});
  assert.deepEqual(data.decks.map(d=>d.id),["b"]);
  assert.deepEqual(data.slides.map(s=>s.id),["b-1"]);
  assert.equal(data.live_cursor,12);
});

test("count-only status updates never allocate or replace card arrays", () => {
  const data=initial(), decks=data.decks, slides=data.slides;
  const info=merge(data,{cursor:10,stats:{deck_count:99,slide_count:128},has_more:false,removed:[],upserts:[]});
  assert.equal(info.changed,false);
  assert.equal(data.decks,decks);
  assert.equal(data.slides,slides);
  assert.equal(data.stats.slide_count,128);
});

test("invalid and stale cursor responses are rejected before changing data", () => {
  const data=initial();
  assert.throws(()=>merge(data,{...updated(),cursor:9}),/Out-of-order/);
  assert.throws(()=>merge(data,{...updated(),upserts:[{deck:{id:"a"},slides:[{deck_id:"b"}]}]}),/Invalid live deck/);
  assert.throws(()=>merge(data,{...updated(),cursor:"11"}),/Invalid live index/);
  assert.equal(data.live_cursor,10);
  assert.deepEqual(data.decks,[oldDeck]);
});
