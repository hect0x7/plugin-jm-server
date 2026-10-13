"""Run the browser-independent sync protocol against a small in-memory server."""
import subprocess
from pathlib import Path


def test_sync_revision_policy_and_device_participation():
    source = Path(__file__).parents[1] / 'src/jm_view_server/static/js/sync.js'
    script = r"""
const vm = require('vm'), fs = require('fs'), assert = require('assert');
const localBookmarks = [{path:'C:/LocalAlbum',timestamp:'2026-01-01T00:00:00Z'}];
const storage = new Map([['plugin_jm_bookmarks',JSON.stringify(localBookmarks)]]), listeners = {}, events = [];
let config = {server_id:'test-server',enabled:true,editable:true,revision:0,
 scopes:{bookmarks:true,progress:true,sequence:true,readerMode:false}};
let entries = {}, posts = 0, failPost = false, holdPost = false, releasePost;
const localStorage = {getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,String(v)),removeItem:k=>storage.delete(k)};
const window = {location:{pathname:'/settings'},addEventListener:(k,f)=>(listeners[k] ||= []).push(f),
 dispatchEvent:e=>{events.push(e);(listeners[e.type]||[]).forEach(f=>f(e));},
 setTimeout:()=>1,clearTimeout:()=>{},setInterval:()=>1};
const context = {window,localStorage,document:{hidden:false,addEventListener:()=>{}},
 CustomEvent:class {constructor(type,options){this.type=type;this.detail=options?.detail;}},
 fetch:async(url,options)=>{
  let data;
  if(url.endsWith('/config')) data=config;
  else if(options?.method==='POST') {
   posts++;
   const changes=JSON.parse(options.body).changes;
   if(holdPost) { holdPost=false; await new Promise(resolve=>releasePost=resolve); }
   if(failPost) throw new Error('network unavailable');
   if(changes.some(c=>c.base_revision!==(entries[c.key]?.revision||0)))
    return {ok:false,status:409,json:async()=>({error:'conflict'})};
   changes.forEach(c=>entries[c.key]={value:c.value,revision:++config.revision});
   data={entries};
  } else data={entries};
  return {ok:true,status:200,json:async()=>JSON.parse(JSON.stringify(data))};
 }};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context);
(async()=>{
 const sync=window.JmvSync; await sync.ready;
 assert.strictEqual(sync.isEnabled(),true,'new browser defaults to participating');
 assert.deepEqual(JSON.parse(storage.get('jmv-sync:test-server')).localBookmarks,localBookmarks,'adopting server data preserves a local bookmark backup');
 assert.strictEqual(posts,0,'default participation does not automatically import old bookmarks');
 await sync.setEnabled(false);
 assert.strictEqual(sync.canonicalPath('C:\\Album\\Page.JPG'),'c:/album/page.jpg');
 assert.strictEqual(sync.canonicalPath('/Album/Page.JPG'),'/Album/Page.JPG');
 assert.strictEqual(sync.canonicalPath('C:/'),'c:/');
 assert.strictEqual(sync.canonicalPath('C:\\'),'c:/');
 assert.strictEqual(sync.canonicalPath('/'),'/');
 assert.strictEqual(sync.canonicalPath('//HOST/Share/'),'//host/share/');
 assert.strictEqual(sync.canonicalPath('//HOST/Share'),'//host/share');
 assert.strictEqual(sync.canonicalPath('\\\\HOST\\Share\\'),'//host/share/');
 assert.strictEqual(sync.canonicalPath('//HOST/Share/child/../'),'//host/share/');
 assert.strictEqual(sync.canonicalPath('C:/Album/./child/../'),'c:/album');
 sync.setRecord('bookmark:c:/album',{path:'C:/Album',timestamp:'2026-01-01T00:00:00Z'});
 await sync.retry(); assert.strictEqual(posts,0,'opt-out sends no data');
 await sync.setEnabled(true);
 assert.deepEqual(JSON.parse(storage.get('jmv-sync:test-server')).localBookmarks,localBookmarks,'re-enabling with an empty server view keeps the original local backup');
 assert.strictEqual(sync.allows('readerMode'),false,'server controls scopes');
 sync.setRecord('preference:readerMode','double'); await sync.retry(); assert.strictEqual(posts,0);
 const key='bookmark:c:/album', value={path:'C:/Album',timestamp:'2026-01-01T00:00:00Z'};
 sync.setRecord(key,value); await sync.retry(); assert.strictEqual(posts,1);
 assert.strictEqual(sync.getRecord(key).path,value.path);
 sync.setRecord(key,value);
 entries[key]={value:null,revision:++config.revision};
 await sync.retry(); assert.strictEqual(posts,1,'stale queued edit cannot revive server deletion');
 assert.strictEqual(sync.getRecord(key),null);
 sync.setRecord(key,value); config.scopes.bookmarks=false; await sync.retry();
 assert.strictEqual(posts,1,'policy removal discards queued writes');
 config.scopes.bookmarks=true; await sync.refresh(); await sync.retry();
 assert.strictEqual(posts,1,'re-enabled policy cannot replay removed queue');
 sync.setRecord(key,value); await sync.setEnabled(false); await sync.retry();
 assert.strictEqual(posts,1,'disabled browser clears unsent queue');
 await sync.setEnabled(true);
 const progressKey='progress:c:/album', sequenceKey='sequence:c:/album';
 entries[progressKey]={value:{image:'C:/Album/old.jpg'},revision:++config.revision};
 entries[sequenceKey]={value:{items:[{type:'page',path:'C:/Album/old.jpg'}]},revision:++config.revision};
 await sync.refresh();
 const progress={image:'C:/Album/new.jpg'}, sequence={items:[{type:'blank',id:'blank-new'}]};
 sync.setRecord(progressKey,progress); sync.setRecord(sequenceKey,sequence);
 failPost=true; await sync.retry();
 assert.strictEqual(sync.getRecord(progressKey).image,progress.image,'offline progress stays local');
 const applied=events.filter(e=>e.type==='jmv:sync-applied').at(-1).detail.entries;
 assert.strictEqual(applied[progressKey].value.image,progress.image,'snapshot event preserves pending progress');
 assert.strictEqual(applied[sequenceKey].value.items[0].id,'blank-new','snapshot preserves pending sequence');
 failPost=false; holdPost=true;
 const inFlight=sync.retry();
 for(let i=0;i<30&&!releasePost;i++) await Promise.resolve();
 assert.ok(releasePost,'patch reached controlled network boundary');
 let refreshed=false; const parallel=sync.refresh().then(()=>refreshed=true);
 await Promise.resolve(); assert.strictEqual(refreshed,false,'refresh awaits pending patch');
 sync.setRecord(progressKey,{image:'C:/Album/newer.jpg'});
 releasePost(); await Promise.all([inFlight,parallel]);
 assert.strictEqual(sync.getRecord(progressKey).image,'C:/Album/newer.jpg','new edit survives accepted earlier patch');
 await sync.retry();
 assert.strictEqual(entries[progressKey].value.image,'C:/Album/newer.jpg','new edit rebased and uploaded');
 assert.strictEqual(sync.getStatus().status,'已同步');
 await sync.setEnabled(false);await sync.refresh();
 assert.strictEqual(sync.isEnabled(),false,'explicitly disabled participation survives refresh');
 config.server_id='another-server'; await sync.refresh();
 assert.strictEqual(sync.isEnabled(),true,'new server identity has its own default');
 config.server_id='test-server'; await sync.refresh();
 assert.strictEqual(sync.isEnabled(),false,'returning to the original server preserves its disabled choice');
 console.log('sync protocol checks passed');
})().catch(e=>{console.error(e);process.exitCode=1;});
"""
    result = subprocess.run(['node', '-e', script, str(source)], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
