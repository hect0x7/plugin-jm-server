"""Small DOM regressions for image identity during Contact Sheet regrouping."""
import subprocess
from pathlib import Path


def test_regroup_reuses_loaded_images_rows_and_updated_operation_indices():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
let writes=0,creates=0;
function node(tag){const events={};return{tag,children:[],dataset:{},attrs:{},className:'',scrollTop:100,isConnected:true,
classList:{contains:n=>n==='show',toggle(){},add(){},remove(){}},
setAttribute(n,v){this.attrs[n]=v},removeAttribute(n){delete this.attrs[n]},addEventListener(n,f){events[n]=f},
emit(n){events[n]({stopPropagation(){}})},
appendChild(x){this.insertBefore(x,null)},insertBefore(x,before){if(x.parent)x.remove();let i=before?this.children.indexOf(before):this.children.length;this.children.splice(i,0,x);x.parent=this;x.isConnected=true},
remove(){if(this.parent)this.parent.children.splice(this.parent.children.indexOf(this),1);this.parent=null;this.isConnected=false},
get lastElementChild(){return this.children.at(-1)},
querySelector(s){return this.querySelectorAll(s)[0]||null},querySelectorAll(s){let all=[];for(let x of this.children){if(s==='[data-reader-page]'?x.dataset.readerPage!==undefined:x.className.split(' ').includes(s.slice(1)))all.push(x);all.push(...x.querySelectorAll(s))}return all},
getBoundingClientRect(){return{top:0,bottom:100}},getAttribute(n){return this.attrs[n]},
set src(v){this.attrs.src=v;writes++},get src(){return this.attrs.src},
set textContent(v){this.text=v;if(v==='')this.children.forEach(x=>x.parent=null),this.children=[]},get textContent(){return this.text}}
}
let grid=node('div'),overlay=node('div'),groups=[{kind:'cover',slots:[null,0],pages:[0]},{kind:'pair',slots:[1,2],pages:[1,2]},{kind:'pair',slots:[3,4],pages:[3,4]},{kind:'pair',slots:[5,null],pages:[5]}];
let rawPages=Array.from({length:6},(_,i)=>{let p=node('div'),im=node('img');im.className='page-img';im.attrs['data-src']='/image/'+i;p.appendChild(im);return p});
const ctx={Map,Set,Array,Number,Math,Date,readerMode:'double',rawPages,activePageIndex:0,readingDirection:'ltr',isSequencePersisted:false,
pageSequence:rawPages.map((_,i)=>({type:'page',pageIndex:i})),localStorage:{getItem:()=> '1'},
document:{getElementById:n=>n==='readerGrid'?grid:n==='readerGridOverlay'?overlay:null,createElement:t=>{if(t==='img')creates++;return node(t)}},
window:{},icon:()=>'',buildDoubleGroups:()=>groups,bindCardDragEvents(){},saveSequenceState(){},applySequenceToDOM(){},updateImagePageType(){},setTimeout(){},clearTimeout(){}};
vm.createContext(ctx);const source=fs.readFileSync('src/jm_view_server/static/js/reader-contact-sheet.js','utf8');
vm.runInContext(source.slice(0,source.indexOf('function moveGridSequenceItem')),ctx);
ctx.rebuildReaderGrid();let cards=Array.from(ctx.readerGridCards.values()),thumbs=cards.map(c=>c.querySelector('.reader-grid-thumb-wrap').children[0]),row=grid.children[2],initialWrites=writes;
ctx.rebuildReaderGrid();assert.equal(creates,6);assert.equal(writes,initialWrites);assert.equal(grid.children[2],row);
groups=[groups[0],{kind:'pair',slots:[1,null],pages:[1]},{kind:'wide',slots:[2,2],pages:[2]},groups[2],groups[3]];
ctx.readerGridTypeRefreshPending=true;ctx.flushReaderGridTypeRefresh();assert.equal(grid.children[3],row);
cards.forEach((c,i)=>{assert.equal(ctx.readerGridCards.get('page:'+i),c);assert.equal(c.querySelector('.reader-grid-thumb-wrap').children[0],thumbs[i])});
assert.equal(writes,initialWrites);assert.equal(creates,6);
ctx.isGridDoublePreview=false;ctx.pageSequence.reverse();ctx.rebuildReaderGrid();assert.equal(grid.children[0],cards[5]);
let card=cards[2],before=ctx.pageSequence.findIndex(x=>x.pageIndex===2);card.querySelector('.reader-grid-insert-btn').emit('click');
assert.equal(ctx.pageSequence[before].type,'blank');assert.equal(ctx.pageSequence[before+1].pageIndex,2);
assert.equal(writes,initialWrites);assert.equal(creates,6);
// Separate all-blank spreads must never reuse the same row or lose cards.
ctx.pageSequence=[{type:'page',pageIndex:0},...Array.from({length:4},(_,i)=>({type:'blank',id:'blank-'+i})),{type:'page',pageIndex:1}];
groups=[{kind:'cover',slots:[null,0],pages:[0]},
 {kind:'pair',slots:[null,null],pages:[],insertedSlots:[0,1]},
 {kind:'pair',slots:[null,null],pages:[],insertedSlots:[0,1]},
 {kind:'pair',slots:[1,null],pages:[1]}];
ctx.isGridDoublePreview=true;ctx.rebuildReaderGrid();
assert.equal(grid.children.length,4);assert.notEqual(grid.children[1],grid.children[2]);
assert.equal(grid.querySelectorAll('.reader-grid-blank').length,4);
for(let n=0;n<4;n++)assert.ok(ctx.readerGridCards.get('blank:blank-'+n).parent);
let firstBlankSpread=grid.children[1],secondBlankSpread=grid.children[2];ctx.rebuildReaderGrid();
assert.equal(grid.children[1],firstBlankSpread);assert.equal(grid.children[2],secondBlankSpread);
assert.equal(grid.querySelectorAll('.reader-grid-blank').length,4);
"""
    result = subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
