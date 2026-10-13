"""Policy saves preserve drafts and feedback across background status updates."""
import subprocess
from pathlib import Path


def test_policy_save_locks_inputs_and_retains_failed_draft():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.dataset={};this.attributes={};this.events={};this.checked=false;this.disabled=false;this.innerHTML='save markup';this.textContent='';this.classes=new Set();this.classList={toggle:(name,value)=>value?this.classes.add(name):this.classes.delete(name)};}
 append(...children){children.forEach(child=>this.appendChild(child));}
 appendChild(child){this.children.push(child);child.parent=this;return child;}
 setAttribute(name,value){this.attributes[name]=value;}
 getAttribute(name){return this.attributes[name];}
 addEventListener(name,fn){this.events[name]=fn;}
 querySelectorAll(selector){const result=[];for(const child of this.children){if(selector==='input'&&child.tag==='input')result.push(child);result.push(...child.querySelectorAll(selector));}return result;}
 closest(selector){let node=this;while(node){if(selector==='.sync-range'&&node.className==='sync-range')return node;node=node.parent;}return null;}
}
const ids=['syncSettings','syncParticipation','syncPolicy','syncServerEnabled','syncRanges','syncSavePolicy','syncRangeCount','syncPolicyHint','syncStatus','syncActiveRanges','syncMergeBookmarks','syncRetry','syncRemote','syncDeviceBadge'];
const elements=Object.fromEntries(ids.map(id=>[id,new Element()])),listeners={};
const keys=['bookmarks','progress','sequence','readerMode','readingDirection','doubleWidthScale','eyeCare','headerHidden','progressHidden','autoNext'];
let state={participating:false,status:'此浏览器未参与同步',config:{editable:true,enabled:false,scopes:Object.fromEntries(keys.map((key,index)=>[key,index<3]))}};
let saves=0,resolveSave,rejectSave;
const sync={getStatus:()=>state,allows:()=>false,ready:Promise.resolve(),
 saveConfig(value){saves++;return new Promise((resolve,reject)=>{resolveSave=()=>{state.config={...state.config,...value};resolve();};rejectSave=reject;});},
 async refresh(){listeners['jmv:sync-status']();},retry(){}};
const context={document:{getElementById:id=>elements[id],createElement:tag=>new Element(tag)},
 icon:()=>'<svg></svg>',console};
context.window={JmvSync:sync,addEventListener:(name,fn)=>listeners[name]=fn,runSettingsUpdate:(target,fn)=>fn()};
vm.createContext(context);vm.runInContext(fs.readFileSync('src/jm_view_server/static/js/sync-settings.js','utf8'),context);
(async()=>{
 await new Promise(resolve=>setImmediate(resolve));
 const inputs=elements.syncRanges.querySelectorAll('input');
 assert.equal(inputs.length,10);assert.equal(new Set(inputs.map(input=>input.dataset.scope)).size,10);
 assert.equal(elements.syncRangeCount.textContent,'已选择 3 项');assert.equal(elements.syncSavePolicy.disabled,true);
 const mode=inputs.find(input=>input.dataset.scope==='readerMode');mode.checked=true;elements.syncRanges.events.change({target:mode});
 assert.equal(elements.syncSavePolicy.disabled,false);assert.equal(elements.syncRangeCount.textContent,'已选择 4 项');
 elements.syncServerEnabled.onclick();
 const saving=elements.syncSavePolicy.onclick();
 assert.equal(elements.syncSavePolicy.attributes['aria-busy'],'true');assert.equal(elements.syncServerEnabled.disabled,true);assert.ok(inputs.every(input=>input.disabled));
 await elements.syncSavePolicy.onclick();assert.equal(saves,1);
 rejectSave(new Error('fixture save failure'));await saving;
 assert.equal(elements.syncSavePolicy.disabled,false);assert.equal(elements.syncServerEnabled.disabled,false);assert.ok(inputs.every(input=>!input.disabled));
 assert.equal(mode.checked,true);assert.equal(elements.syncServerEnabled.attributes['aria-checked'],'true');
 assert.equal(elements.syncPolicyHint.textContent,'保存失败，修改已保留，请重试');
 state.status='已同步';listeners['jmv:sync-status']();
 assert.equal(elements.syncPolicyHint.textContent,'保存失败，修改已保留，请重试');assert.equal(mode.checked,true);
 const retry=elements.syncSavePolicy.onclick();resolveSave();await retry;
 assert.equal(saves,2);assert.equal(state.config.scopes.readerMode,true);assert.equal(elements.syncSavePolicy.disabled,true);
 assert.equal(elements.syncPolicyHint.textContent,'保存后对所有设备生效。');
 state.config.editable=false;listeners['jmv:sync-status']();assert.equal(elements.syncPolicy.hidden,true);assert.equal(elements.syncRemote.hidden,false);
})().catch(error=>{console.error(error);process.exitCode=1});
"""
    subprocess.run(['node', '-e', script], cwd=Path(__file__).parents[1],
                   check=True, capture_output=True, text=True)
