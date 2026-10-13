"""Stable page identities when auto-next appends books after contact-sheet edits."""
import subprocess
from pathlib import Path


def test_append_books_preserves_page_identity_and_double_grouping():
    root = Path(__file__).resolve().parents[1]
    script = r"""
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const read = name => fs.readFileSync('src/jm_view_server/static/js/' + name, 'utf8');
function element(tag) {
  return {tag, children: [], dataset: {}, attributes: {},
    appendChild(child) { this.children.push(child); child.parentNode = this; },
    setAttribute(name, value) { this.attributes[name] = value; },
    getAttribute(name) { return this.attributes[name]; },
    querySelector() { return this.children[0]; }
  };
}
const oldPages = [0, 1, 2].map(i => {
  const page = element('div'), image = element('img');
  page.id = 'page_' + i; image.dataset.readerWide = '0'; page.appendChild(image); return page;
});
const stream = element('div');
// Contact-sheet edits rearrange DOM, including a virtual blank in the sequence.
[oldPages[2], oldPages[0], oldPages[1]].forEach(p => stream.appendChild(p));
const select = element('select'), jump = element('select');
const elements = {stream, pageselect: select, jumpSelect: jump};
let gridCalls = 0, scans = 0, jumped = null;
const context = {
  document: {getElementById: id => elements[id], createElement: element,
    querySelectorAll() { throw new Error('DOM order must never replace stable page identities'); }},
  rawPages: oldPages.slice(), pages: oldPages.slice(), TOTAL: 3,
  originalSequence: [0,1,2].map(pageIndex => ({type:'page',pageIndex})),
  pageSequence: [{type:'page',pageIndex:2},{type:'blank',id:'inserted'},
                 {type:'page',pageIndex:0},{type:'page',pageIndex:1}],
  ALBUM_RANGES: [{start:0,end:2,path:'/books/first',key:'jmv-progress:/books/first'}],
  activePageIndex: 1, readerMode:'double', readingDirection:'ltr',
  isPagedMode() { return context.readerMode === 'single'; },
  rebuildReaderGrid() { gridCalls++; assert.equal(context.pages,context.rawPages); },
  rebuildDoubleGroups() { context.doubleGroups = context.buildDoubleGroups(); },
  gotoPage(idx) { jumped = idx; }
};
context.window = context;
context.JmvImageLoader = {scan(node) {
  scans++; assert.equal(node, stream);
  assert.equal(context.ALBUM_RANGES.at(-1).end, context.TOTAL - 1);
  assert.equal(context.pages, context.rawPages);
}};
vm.createContext(context);
const preferences = read('reader-preferences.js');
vm.runInContext(preferences.slice(preferences.indexOf('function appendNextAlbumData'),
                                  preferences.indexOf('function setImageRotation')), context);
const modes = read('reader-modes.js');
vm.runInContext(modes.slice(modes.indexOf('function isWidePage'), modes.indexOf('function findDoubleGroupIndex')),context);
context.appendNextAlbumData({images:[{data_original:'/image/a'},{data_original:'/image/b'}],
                            full_path:'/books/second',next_dir_path:'/books/third',title:'Second'});
assert.equal(context.TOTAL,5);
assert.equal(context.pages[0],oldPages[0]); assert.equal(context.pages[2],oldPages[2]);
assert.equal(context.pages[3].id,'page_3'); assert.equal(context.pages[4].id,'page_4');
assert.equal(context.pages[3].querySelector().getAttribute('data-original'),'/image/a');
assert.deepEqual(JSON.parse(JSON.stringify(context.pageSequence)).map(i => i.pageIndex ?? i.id),[2,'inserted',0,1,3,4]);
assert.deepEqual(JSON.parse(JSON.stringify(context.originalSequence)).map(i => i.pageIndex),[0,1,2,3,4]);
assert.deepEqual(Array.from(context.doubleGroups.flatMap(g => g.pages)).sort(),[0,1,2,3,4]);
assert.equal(context.ALBUM_RANGES[1].path,'/books/second');
assert.equal(context.ALBUM_RANGES[1].key,'jmv-progress:/books/second');
assert.equal(select.children[0].value,'3'); assert.equal(jump.children[1].value,'4');
assert.equal(gridCalls,1); assert.equal(scans,1); assert.equal(jumped,null);
// Loaded landscape pages are still indexed by the same identity after append.
context.pages[3].querySelector().dataset.readerWide = '1';
const landscape = context.buildDoubleGroups().find(g => g.pages.includes(3));
assert.equal(landscape.kind,'wide'); assert.deepEqual(Array.from(landscape.pages),[3]);
// Single-page auto-next advances to the first newly appended stable page.
context.readerMode = 'single'; context.activePageIndex = 4;
context.appendNextAlbumData({images:[{data_original:'/image/c'}],full_path:'/books/third',next_dir_path:null,title:'Third'});
assert.equal(context.TOTAL,6); assert.equal(jumped,5);
assert.equal(context.pageSequence.at(-1).pageIndex,5);
assert.equal(context.originalSequence.at(-1).pageIndex,5);
assert.equal(context.ALBUM_RANGES[2].start,5); assert.equal(scans,2); assert.equal(gridCalls,2);
assert.equal(context.pages[0],oldPages[0]);
assert.deepEqual(Array.from(context.buildDoubleGroups().flatMap(g => g.pages)).sort(),[0,1,2,3,4,5]);
"""
    subprocess.run(['node', '-e', script], cwd=root, check=True, capture_output=True, text=True)
