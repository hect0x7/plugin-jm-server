"""Video previews keep view-local loading and a usable missing-thumbnail fallback."""
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


ROOT = Path(__file__).resolve().parents[1]


class Images(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = []

    def handle_starttag(self, tag, attrs):
        if tag == 'img':
            self.images.append(dict(attrs))


def test_video_template_uses_thumbnail_url_and_keeps_lazy_grid():
    env = Environment(loader=FileSystemLoader(ROOT / 'src/jm_view_server/templates'))
    video = dict(name='example.mp4', type='file', jm_view=False, is_link=False,
                 first_img_url=dict(data_thumb='/api/thumb?path=example.mp4&source=system',
                                    data_original='/video/example.mp4', thumbnail_source='system'),
                 manage_quoted_path='example.mp4', quoted_path='example.mp4', href='/video/example.mp4',
                 size='1 MB', ctime='')
    html = env.get_template('index.html').render(data=dict(
        files=[video], currentPath='/media', defaultPath='/media', drivers=[],
        lan_ip='example.com', port=80, os_type='windows'))
    parsed = Images()
    parsed.feed(html)
    previews = [img for img in parsed.images if 'data-system-thumbnail' in img]
    assert len(previews) == 2
    assert previews[0]['src'] == video['first_img_url']['data_thumb']
    assert 'src' not in previews[1]
    assert previews[1]['data-thumb-src'] == video['first_img_url']['data_thumb']
    assert all(img['onerror'] and img['loading'] == 'lazy' for img in previews)
    assert html.count('class="video-thumbnail-fallback"') == 2


def test_column_video_loads_only_thumbnail_and_uses_shared_retry():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/jm_view_server/static/js/column-view.js','utf8');
const start=source.indexOf("        if (file.first_img_url && file.first_img_url.thumbnail_source === 'system') {");
const end=source.indexOf("        var name =",start);
const classes=new Set(),events={};
const preview={addEventListener:(name,fn)=>events[name]=fn};let retried=null;
const fileIcon={classList:{add:name=>classes.add(name)},appendChild:img=>{assert.equal(img,preview);}};
const context={window:{JmvRetrySystemThumbnail:img=>{retried=img;}},file:{first_img_url:{thumbnail_source:'system',data_thumb:'/api/thumb?source=system',data_original:'/video/example.mp4'}},fileIcon,main:{classList:{add:name=>classes.add(name)}},document:{createElement:tag=>{assert.equal(tag,'img');return preview;}}};
vm.runInNewContext(source.slice(start,end),context);
assert.equal(preview.src,'/api/thumb?source=system');
assert.equal(preview.loading,'lazy');assert.equal(preview.alt,'');
assert.ok(fileIcon.innerHTML.includes('<svg'));assert.ok(classes.has('has-video-thumbnail'));
events.error();assert.equal(retried,preview);assert.ok(fileIcon.innerHTML.includes('<svg'));
"""
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)


def test_system_thumbnail_retry_is_bounded_and_cancels_detached_or_hidden_images():
    script = r"""
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('src/jm_view_server/static/js/app.js','utf8');
const events={},pending=new Map();let id=0;
const context={WeakMap,Map,Set,window:{addEventListener:(name,fn)=>events[name]=fn},
setTimeout:(fn,delay)=>{pending.set(++id,{fn,delay});return id;},clearTimeout:timer=>pending.delete(timer)};
vm.runInNewContext(source.slice(source.indexOf('/* ---------- 系统缩略图的有界重试 ---------- */')),context);
function image(){const classes=new Set();return {isConnected:true,hidden:false,attributes:{src:'/api/thumb?source=system'},writes:[],events:{},
parentElement:{classList:{add:name=>classes.add(name),remove:name=>classes.delete(name)},getClientRects:()=>[{}]},
getAttribute(name){return this.attributes[name]||null;},removeAttribute(name){delete this.attributes[name];},
set src(value){this.writes.push(value);this.attributes.src=value;},addEventListener(name,fn){this.events[name]=fn;},classes};}
function tick(delay){const [timer,job]=pending.entries().next().value;assert.equal(job.delay,delay);pending.delete(timer);job.fn();}
const retry=context.window.JmvRetrySystemThumbnail;
const img=image();retry(img);assert.equal(img.hidden,true);assert.ok(img.classes.has('thumbnail-failed'));
retry(img);assert.equal(pending.size,1);tick(1000);assert.deepEqual(img.writes,['/api/thumb?source=system']);
retry(img);tick(2000);retry(img);assert.equal(pending.size,0);assert.equal(img.writes.length,2);
img.events.load();assert.equal(img.hidden,false);assert.equal(img.classes.has('thumbnail-failed'),false);
const detached=image();retry(detached);detached.isConnected=false;tick(1000);assert.equal(detached.writes.length,0);
const hidden=image();retry(hidden);hidden.parentElement.getClientRects=()=>[];tick(1000);assert.equal(hidden.writes.length,0);
const deferred=image();deferred.attributes={};retry(deferred);assert.equal(pending.size,0);
const leaving=image();retry(leaving);events.pagehide();assert.equal(pending.size,0);retry(leaving);assert.equal(pending.size,0);
events.pageshow();assert.equal(pending.size,1);tick(1000);assert.equal(leaving.writes.length,1);
retry(leaving);tick(2000);retry(leaving);assert.equal(pending.size,0);
"""
    subprocess.run(['node', '-e', script], cwd=ROOT, check=True, capture_output=True, text=True)
