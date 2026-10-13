"""Execute queueing, watchdog isolation and BFCache against small DOM mocks."""
import subprocess
from pathlib import Path

import pytest


def test_quarter_turns_fit_portrait_and_wide_page_boxes():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/jm_view_server/static/js/reader-preferences.js','utf8');
const context={};vm.createContext(context);
vm.runInContext(source.slice(source.indexOf('function updateImageRotationFit(')),context);
for(const [width,height] of [[480,720],[480,2200],[960,600]]) {
 const props={};const image={naturalWidth:width,naturalHeight:height,dataset:{},style:{setProperty(k,v){props[k]=v}}};
 for(const angle of [90,270]) {
  context.setImageRotation(image,angle);const scale=Number(props['--reader-quarter-turn-fit']);
  assert.ok(height*scale<=width+1e-6);assert.ok(width*scale<=height+1e-6);
  assert.match(image.style.transform,/scale\(var\(--reader-rotation-fit, 1\)\)/);
 }
 context.setImageRotation(image,0);assert.equal(image.style.transform,'rotate(0deg)');
 context.setImageRotation(image,180);assert.equal(image.style.transform,'rotate(180deg)');
}
const props={},pending={naturalWidth:1,naturalHeight:1,clientWidth:190,clientHeight:285,style:{setProperty(k,v){props[k]=v}}};
context.updateImageRotationFit(pending);assert.ok(285*Number(props['--reader-quarter-turn-fit'])<=190+1e-6);
pending.naturalWidth=960;pending.naturalHeight=600;context.updateImageRotationFit(pending);
assert.equal(Number(props['--reader-quarter-turn-fit']),0.625);
"""
    subprocess.run(['node', '-e', script], cwd=Path(__file__).resolve().parents[1],
                   check=True, capture_output=True, text=True)


HARNESS = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b});return{promise,resolve,reject}}
function setup(mobile=true){
 let now=0,next=1,blobId=0,observer;const timers=new Map(),events={},requests=[],images=[],pages=[],revoked=[],blobs=[],decodeJobs=[],replacements=[];
 function node(tag){const listeners={},classes=new Set();return{tag,dataset:{},attrs:{},style:{minHeight:''},children:[],isConnected:true,naturalHeight:0,height:100,top:0,
 classList:{add:n=>classes.add(n),remove:n=>classes.delete(n),contains:n=>classes.has(n)},
 addEventListener(n,f){(listeners[n]||(listeners[n]=[])).push(f)},emit(n){(listeners[n]||[]).forEach(f=>f({stopPropagation(){}}))},
 setAttribute(n,v){this.attrs[n]=v},getAttribute(n){return this.attrs[n]},removeAttribute(n){delete this.attrs[n]},
 closest(){return this.parent||null},matches(){return tag==='img'},
 querySelector(s){return this.children.find(x=>s==='.page-img'?x.tag==='img':x.className==='image-load-retry')||null},
 appendChild(x){x.parent=this;this.children.push(x)},remove(){this.parent.children=this.parent.children.filter(x=>x!==this)},
 getBoundingClientRect(){return{top:this.top,bottom:this.top+this.height,height:this.height}},
 cloneNode(){assert.equal(this.attrs.src,undefined);let x=node(tag);x.attrs={...this.attrs};x.dataset={...this.dataset};x.style={...this.style};classes.forEach(c=>x.classList.add(c));return x},
 replaceWith(x){let i=this.parent.children.indexOf(this);this.parent.children[i]=x;x.parent=this.parent;this.parent=null;this.isConnected=false},
 decode(){let d=deferred();decodeJobs.push({image:this,...d});return d.promise},
 set src(v){this.attrs.src=v;this.currentSrc=v},get src(){return this.attrs.src}}}
 function image(top=0){let p=node('div'),i=node('img');p.top=top;i.attrs['data-src']='/view_file?path=fixture'+images.length;i.attrs['data-original']=i.attrs['data-src'];i.classList.add('lazyload');p.appendChild(i);pages.push(p);images.push(i);return i}
 const doc={visibilityState:'visible',documentElement:{clientHeight:600},createElement:node,
 querySelectorAll:()=>pages.map(p=>p.querySelector('.page-img')),getElementById:()=>button,addEventListener:(n,f)=>events[n]=f};
 let button=node('a');
 class TestURL extends URL{}
 TestURL.createObjectURL=b=>{blobs.push(b);return'blob:test/'+(++blobId)};TestURL.revokeObjectURL=u=>revoked.push(u);
 const ctx={URL:TestURL,Blob,Uint8Array,AbortController,navigator:{onLine:true},location:{origin:'https://example.com'},Date:{now:()=>now},innerHeight:600,
 document:doc,matchMedia:()=>({matches:mobile}),addEventListener:(n,f)=>events[n]=f,
 setTimeout(f,delay){const id=next++;timers.set(id,{f,due:now+delay});return id},clearTimeout:id=>timers.delete(id),requestAnimationFrame:f=>ctx.setTimeout(f,1),
 dispatchEvent:e=>replacements.push(e),CustomEvent:function(n,o){this.type=n;this.detail=o.detail},
 readerMode:'scroll',pages,doubleGroups:[],
 fetch(url,options){let d=deferred();requests.push({url,options,...d});return d.promise},
 IntersectionObserver:function(callback,options){observer={callback,options,observe(){},unobserve(){},disconnect(){}};return observer}};
 ctx.window=ctx;vm.createContext(ctx);vm.runInContext(fs.readFileSync('src/jm_view_server/static/js/image-loader.js','utf8'),ctx);
 function advance(ms){let end=now+ms;while(true){let jobs=[...timers.entries()].filter(([,t])=>t.due<=end).sort((a,b)=>a[1].due-b[1].due);if(!jobs.length)break;let[id,t]=jobs[0];timers.delete(id);now=t.due;t.f()}now=end}
 async function flush(){for(let i=0;i<14;i++)await Promise.resolve()}
 function response(index,status=200,mime='image/png',expected=3){const waits=[];let done=false;const reader={read(){let d=deferred();waits.push(d);return d.promise},cancel(){done=true;return Promise.resolve()}};
 requests[index].resolve({status,ok:status>=200&&status<300,headers:{get:n=>n==='Content-Type'?mime:n==='Content-Length'?String(expected):null},body:{getReader:()=>reader}});
 return{chunk(bytes){assert.ok(waits.length);waits.shift().resolve({done:false,value:new Uint8Array(bytes)})},end(){assert.ok(waits.length);waits.shift().resolve({done:true})},get cancelled(){return done}}
 }
 async function body(index,status=200,mime='image/png'){let r=response(index,status,mime);await flush();if(status>=200&&status<300&&mime!=='text/html'){r.chunk([1,2,3]);await flush();r.end();await flush()}return r}
 async function finishDecode(index=0){let d=decodeJobs[index];d.image.naturalHeight=100;d.resolve();await flush();advance(2);await flush()}
 return{ctx,image,pages,images,events,requests,revoked,blobs,decodeJobs,replacements,advance,flush,response,body,finishDecode,button,get observer(){return observer}}
}
"""


def run(script):
    result = subprocess.run(['node', '-e', HARNESS + '\n(async()=>{' + script +
                             '\n})().catch(e=>{console.error(e);process.exitCode=1})'],
                            cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize('mobile,margin', [(True, '160px 0px'), (False, '600px 0px')])
def test_network_caps_and_loadall_preserve_http_url_cache(mobile, margin):
    run(f'const h=setup({str(mobile).lower()});' + r"""
const loader=h.ctx.JmvImageLoader;const items=Array.from({length:8},()=>h.image());
items.forEach(i=>{loader.load(i);loader.load(i)});assert.equal(h.requests.length,4);
loader.loadAll();loader.loadAll();assert.equal(h.requests.length,6);
assert.equal(h.button.attrs['aria-busy'],'true');
h.requests.forEach((r,i)=>{assert.equal(r.url,'https://example.com/view_file?path=fixture'+i);assert.equal(r.options.cache,undefined);assert.equal(r.options.headers,undefined)});
await h.body(0);assert.equal(h.decodeJobs.length,1);await h.finishDecode();
assert.equal(h.requests.length,7);assert.equal(items[0].dataset.imageState,'loaded');assert.equal(h.revoked.length,1);
assert.equal(items[0].classList.contains('lazyload'),false);loader.loadAll();assert.equal(h.requests.length,7);
""" + f"assert.equal(h.observer.options.rootMargin,'{margin}');")


def test_continuing_body_progress_beyond_30_seconds_is_not_timeout():
    run(r"""
const h=setup(),i=h.image();h.ctx.JmvImageLoader.load(i);const r=h.response(0,200,'image/png',6);await h.flush();
h.advance(29000);r.chunk([1,2,3]);await h.flush();h.advance(29000);
r.chunk([4,5,6]);await h.flush();r.end();await h.flush();await h.finishDecode();
assert.equal(i.dataset.imageState,'loaded');assert.equal(h.blobs[0].size,6);
""")


def test_loadall_retries_network_loss_and_503_without_manual_input():
    run(r"""
const h=setup(),i=h.image();h.ctx.JmvImageLoader.loadAll();h.requests[0].reject(new TypeError('connection lost'));await h.flush();
assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/连接失败/);h.advance(1000);assert.equal(h.requests.length,2);
await h.body(1,503);assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/HTTP 503/);h.advance(2000);assert.equal(h.requests.length,3);
await h.body(2);await h.finishDecode();assert.equal(i.dataset.imageState,'loaded');
assert.equal(h.pages[0].querySelector('.image-load-retry'),null);assert.equal(h.button.attrs['aria-busy'],'false');
""")


def test_header_timeout_continues_loadall_and_late_fetch_does_not_settle_new_request():
    run(r"""
const h=setup(),i=h.image();h.ctx.JmvImageLoader.loadAll();h.advance(45000);await h.flush();
assert.equal(h.requests[0].options.signal.aborted,true);assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/传输暂无响应/);
h.advance(1000);assert.equal(h.requests.length,2);h.response(0);await h.flush();assert.equal(h.decodeJobs.length,0);
await h.body(1);await h.finishDecode();assert.equal(i.dataset.imageState,'loaded');
""")


def test_404_is_explicit_hard_failure_but_other_images_finish():
    run(r"""
const h=setup(),a=h.image(),b=h.image();h.ctx.JmvImageLoader.loadAll();await h.body(0,404);await h.body(1);await h.finishDecode();
assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/HTTP 404/);assert.equal(b.dataset.imageState,'loaded');
h.advance(100000);assert.equal(h.requests.length,2);assert.match(h.button.title,/1 张失败/);assert.equal(h.button.attrs['aria-busy'],'false');
""")


def test_decode_queue_limit_timer_starts_on_active_decode_and_failure_preserves_attributes():
    run(r"""
const h=setup(),items=Array.from({length:6},()=>h.image());items[0].dataset.rotate='90';items[0].style.transform='rotate(90deg)';
h.ctx.JmvImageLoader.loadAll();for(let j=0;j<6;j++)await h.body(j);
assert.equal(h.decodeJobs.length,2);h.advance(19000);
await h.finishDecode(0);assert.equal(h.decodeJobs.length,3);h.advance(1000);await h.flush();
assert.match(h.pages[1].querySelector('.image-load-retry').textContent,/解码超时/);
// The third decode has its own 20-second clock, not the first job's clock.
assert.equal(items[2].dataset.imageState,'loading');assert.equal(h.decodeJobs.length,4);
""")


def test_three_decode_failures_become_hard_and_replacement_keeps_original_identity():
    run(r"""
const h=setup(),i=h.image();i.dataset.rotate='90';i.style.transform='rotate(90deg)';h.ctx.JmvImageLoader.loadAll();
for(let n=0;n<3;n++){await h.body(n);h.decodeJobs[n].reject(new Error('decoder'));await h.flush();if(n<2)h.advance([1000,2000][n])}
const current=h.ctx.JmvImageLoader.currentImage(i);assert.notEqual(current,i);assert.equal(current.dataset.rotate,'90');assert.equal(current.style.transform,'rotate(90deg)');
assert.equal(current.getAttribute('data-original'),i.getAttribute('data-original'));assert.equal(h.revoked.length,3);
assert.equal(h.requests.length,3);assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/解码失败/);
""")


def test_pagehide_and_visibility_pause_preserve_completed_images_and_resume_sticky_queue():
    run(r"""
const h=setup(),a=h.image(),b=h.image(2200);h.ctx.JmvImageLoader.loadAll();await h.body(0);await h.finishDecode();const source=a.src;
h.events.pagehide();assert.equal(h.requests[1].options.signal.aborted,true);assert.equal(a.src,source);
h.advance(100000);h.events.pageshow({persisted:true});assert.equal(h.requests.length,3);
await h.body(2);await h.finishDecode(1);assert.equal(b.dataset.imageState,'loaded');assert.equal(a.src,source);
h.ctx.document.visibilityState='hidden';h.events.visibilitychange();h.ctx.document.visibilityState='visible';h.events.visibilitychange();assert.equal(h.requests.length,3);
""")


def test_appended_album_joins_sticky_loadall_and_offline_returns_automatically():
    run(r"""
const h=setup(),a=h.image();h.ctx.JmvImageLoader.loadAll();await h.body(0);await h.finishDecode();
const b=h.image(2200);h.ctx.JmvImageLoader.scan();assert.equal(h.requests.length,2);
h.ctx.navigator.onLine=false;h.events.offline();assert.equal(h.requests[1].options.signal.aborted,true);
h.ctx.navigator.onLine=true;h.events.online();assert.equal(h.requests.length,3);await h.body(2);await h.finishDecode(1);
assert.equal(b.dataset.imageState,'loaded');
""")


def test_body_inactivity_and_truncation_show_distinct_error_causes():
    run(r"""
const h=setup(),i=h.image();h.ctx.JmvImageLoader.loadAll();let r=h.response(0,200,'image/png',6);await h.flush();r.chunk([1,2,3]);await h.flush();
h.advance(45000);await h.flush();assert.equal(r.cancelled,true);assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/传输暂无响应/);
h.advance(1000);r=h.response(1,200,'image/png',6);await h.flush();r.chunk([1,2,3]);await h.flush();r.end();await h.flush();
assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/接收不完整/);assert.equal(h.decodeJobs.length,0);
""")


def test_late_decode_cannot_release_slot_or_mark_replacement_loaded():
    run(r"""
const h=setup(),i=h.image();h.ctx.JmvImageLoader.loadAll();await h.body(0);h.advance(20000);await h.flush();
const next=h.ctx.JmvImageLoader.currentImage(i);h.advance(1000);await h.body(1);assert.equal(h.decodeJobs.length,2);
await h.finishDecode(0);assert.equal(next.dataset.imageState,'loading');await h.finishDecode(1);assert.equal(next.dataset.imageState,'loaded');
assert.equal(h.revoked.length,2);assert.equal(h.requests.length,2);
""")


def test_double_spread_partner_and_visible_priority_are_retained():
    run(r"""
const h=setup(),loader=h.ctx.JmvImageLoader;
for(let n=0;n<4;n++)loader.load(h.image());const far=h.image(2200),visible=h.image(0),partner=h.image(1800);
h.ctx.readerMode='double';h.ctx.doubleGroups=[{pages:[5,6]}];h.pages[5].dataset.doubleGroup='0';h.pages[6].dataset.doubleGroup='0';
loader.load(far);h.observer.callback([{isIntersecting:true,target:h.pages[5]}]);
await h.body(0);await h.finishDecode();assert.equal(h.requests[4].url,'https://example.com/view_file?path=fixture5');
await h.body(1);await h.finishDecode(1);assert.equal(h.requests[5].url,'https://example.com/view_file?path=fixture6');
""")


def test_html_login_response_has_explicit_authentication_error():
    run(r"""
const h=setup(),i=h.image();h.ctx.JmvImageLoader.loadAll();await h.body(0,200,'text/html');
assert.equal(i.dataset.imageState,'error');assert.equal(h.decodeJobs.length,0);assert.match(h.pages[0].querySelector('.image-load-retry').textContent,/登录/);
""")
