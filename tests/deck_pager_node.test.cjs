const test = require('node:test');
const assert = require('node:assert/strict');
const {PAGE_SIZE, paginate} = require('../web/static/js/deck-pager.js');

const decks = Array.from({length: 14657}, (_, i) => ({
  id: `deck-${i}`,
  file_name: `Archive-${String(i).padStart(5, '0')}.PPTX`,
  _searchDeck: `archive-${String(i).padStart(5, '0')}.pptx`,
}));

test('page size and stable order are bounded across a real-sized archive', () => {
  assert.equal(PAGE_SIZE, 100);
  const first = paginate(decks);
  assert.equal(first.total, 14657);
  assert.equal(first.pages, 147);
  assert.equal(first.page, 0);
  assert.equal(first.entries.length, 100);
  assert.strictEqual(first.entries[0], decks[0]);
  const last = paginate(decks, '', 146);
  assert.equal(last.entries.length, 57);
  assert.equal(last.start, 14600);
  assert.strictEqual(last.entries[56], decks[14656]);
  assert.strictEqual(paginate(decks, '', 999).entries[0], decks[14600]);
  assert.strictEqual(paginate(decks, '', -20).entries[0], decks[0]);
  assert.equal(decks.length, 14657);
});

test('search sees filenames on any page without changing source order', () => {
  const target = paginate(decks, 'ARCHIVE-14656', 0);
  assert.equal(target.total, 1);
  assert.equal(target.pages, 1);
  assert.strictEqual(target.entries[0], decks[14656]);
  const sample = paginate(decks, 'archive-0');
  assert.equal(sample.total, 10000);
  assert.strictEqual(sample.entries[0], decks[0]);
});

test('narrowing search clamps an obsolete page and handles zero matches', () => {
  const page = paginate(decks, 'archive-14656', 95);
  assert.equal(page.page, 0);
  assert.equal(page.entries.length, 1);
  const empty = paginate(decks, 'missing-name', 900);
  assert.deepEqual(empty, {entries: [], page: 0, pages: 0, start: 0, total: 0});
  assert.deepEqual(paginate([], ''), empty);
});

test('normalization, missing names and invalid page values are safe', () => {
  const sample = [{file_name: 'Long Filename.MD'}, {file_name: ''}, {}];
  assert.equal(paginate(sample, ' filename ').total, 1);
  assert.equal(paginate(sample, 'Md').total, 1);
  assert.equal(paginate(sample, '', Number.POSITIVE_INFINITY).page, 0);
  assert.equal(paginate(sample, '', NaN).page, 0);
});
