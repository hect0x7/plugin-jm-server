(function() {
  var PLACEHOLDER = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
  var mobile = window.matchMedia('(max-width: 860px), (pointer: coarse)').matches;
  var observed = new WeakSet(), states = new WeakMap(), known = new Set();
  var queue = [], decodeQueue = [], active = 0, decoding = 0;
  var suspended = false, batching = false, allRequested = false, allNotified = false;
  function currentImage(image) { var state = states.get(image); return state ? state.image : image; }
  function alive(state, token) { return state.token === token && !token.finished; }
  function revoke(token) { if (token.renderUrl) { URL.revokeObjectURL(token.renderUrl); token.renderUrl = ''; } }
  function release(state, token) {
    if (!alive(state, token)) return false;
    token.finished = true; clearTimeout(token.watchdog);
    if (token.decoding) { token.decoding = false; decoding--; }
    token.blob = null; token.chunks = null; revoke(token);
    state.loading = false; active--;
    return true;
  }
  function distance(image) {
    var parent = image.closest('.scramble-page') || image;
    var viewport = window.innerHeight || document.documentElement.clientHeight;
    function measure(node) { var rect = node.getBoundingClientRect(); return rect.bottom >= 0 && rect.top <= viewport ? 0 : (rect.top > viewport ? rect.top - viewport : -rect.bottom); }
    var result = measure(parent);
    if (typeof readerMode !== 'undefined' && readerMode === 'double' && parent.dataset.doubleGroup !== undefined) {
      var group = doubleGroups[Number(parent.dataset.doubleGroup)];
      if (group) group.pages.forEach(function(index) { if (pages[index]) result = Math.min(result, measure(pages[index])); });
    }
    return result;
  }
  function bind(image) {
    var state = states.get(image);
    if (state) return state;
    state = {image: image, loading: false, queued: false, attempts: 0, decodeFailures: 0, failed: false, hard: false, retryTimer: null, token: null};
    states.set(image, state); known.add(state); return state;
  }
  function replacePendingImage(state) {
    var previous = state.image, height = previous.getBoundingClientRect().height;
    previous.removeAttribute('src');
    var image = previous.cloneNode(false);
    if (state.minimumHeight === undefined) state.minimumHeight = previous.style.minHeight;
    if (height > 0) image.style.minHeight = height + 'px';
    state.image = image; states.set(image, state); image.src = PLACEHOLDER;
    previous.replaceWith(image); observed.delete(previous);
    observer.unobserve(image.closest('.scramble-page') || previous);
    window.dispatchEvent(new CustomEvent('jmv:reader-image-replaced', {detail: {previous: previous, image: image}}));
    observe(image);
  }
  function errorUI(state, token, name, retrying) {
    var image = state.image, parent = image.closest('.scramble-page');
    image.dataset.imageState = 'error';
    if (!parent) return;
    parent.classList.add('image-load-error');
    var button = parent.querySelector('.image-load-retry');
    if (!button) {
      button = document.createElement('button'); button.type = 'button'; button.className = 'image-load-retry';
      button.addEventListener('click', function(event) { event.stopPropagation(); state.attempts = state.decodeFailures = 0; state.hard = false; load(state.image, true); });
      parent.appendChild(button);
    }
    var reason = name === 'AuthError' ? '登录已失效，请重新登录' :
      token.status === 404 ? '原图不存在（HTTP 404）' : token.status === 403 ? '无权访问原图（HTTP 403）' :
      name === 'EncodingError' ? '图片解码失败' : name === 'TimeoutError' ? (token.phase === 'decode' ? '图片解码超时' : '图片传输暂无响应') :
      name === 'LengthMismatch' ? '图片接收不完整' : name === 'TypeError' ? (token.phase === 'body' ? '图片接收中断' : '图片连接失败') :
      token.status ? '图片请求失败（HTTP ' + token.status + '）' : '图片连接失败';
    button.textContent = reason + (retrying ? ' · 自动重试中' : ' · 点击重试');
  }
  function updateAll() {
    if (!allRequested) return;
    var items = Array.from(known).filter(function(s) { return s.image.isConnected !== false; });
    var loaded = items.filter(function(s) { return s.image.dataset.imageState === 'loaded'; }).length;
    var hard = items.filter(function(s) { return s.hard; }).length;
    var complete = loaded === items.length && items.length > 0;
    var terminal = complete || (loaded + hard === items.length && items.length > 0);
    var button = document.getElementById('loadAll');
    if (button) { button.setAttribute('aria-busy', terminal ? 'false' : 'true'); button.title = '加载全部：' + loaded + '/' + items.length + (hard ? '，' + hard + ' 张失败' : ''); }
    if (terminal && !allNotified) {
      allNotified = true;
      if (typeof window.toast === 'function') window.toast(complete ? '全部图片加载完成' : '已加载 ' + loaded + ' 张，' + hard + ' 张无法加载，请查看具体原因');
    }
  }
  function fail(state, token, name) {
    if (!alive(state, token)) return;
    state.failed = true;
    if (token.phase === 'decode') state.decodeFailures++;
    state.hard = name === 'AuthError' || (name === 'HTTPError' && token.status !== 408 && token.status !== 429 && token.status < 500) || state.decodeFailures >= 3;
    token.controller.abort(); if (token.reader) token.reader.cancel().catch(function() {});
    release(state, token);
    if (token.phase === 'decode') replacePendingImage(state);
    var retrying = !state.hard && (allRequested || state.attempts < 3);
    errorUI(state, token, name, retrying);
    if (retrying && !suspended) {
      state.retryTimer = setTimeout(function() { state.retryTimer = null; load(state.image); }, [1000, 2000, 4000, 8000, 15000][Math.min(state.attempts - 1, 4)]);
    }
    drainDecode(); drain(); updateAll();
  }
  function watch(state, token, timeout) {
    clearTimeout(token.watchdog);
    token.watchdog = setTimeout(function() { fail(state, token, 'TimeoutError'); }, timeout);
  }
  function loaded(state, token) {
    if (!alive(state, token)) return;
    var image = state.image;
    release(state, token); state.failed = false; state.decodeFailures = 0;
    image.dataset.imageState = 'loaded'; image.classList.remove('lazyload');
    if (state.minimumHeight !== undefined) { image.style.minHeight = state.minimumHeight; state.minimumHeight = undefined; }
    var parent = image.closest('.scramble-page');
    if (parent) { parent.classList.remove('image-load-error'); var button = parent.querySelector('.image-load-retry'); if (button) button.remove(); }
    observer.unobserve(parent || image); drainDecode(); drain(); updateAll();
  }
  function drainDecode() {
    if (suspended) return;
    while (decoding < 2 && decodeQueue.length) {
      var job = decodeQueue.shift(), state = job.state, token = job.token;
      if (!alive(state, token)) continue;
      token.phase = 'decode'; token.decoding = true; decoding++; token.progress = Date.now(); watch(state, token, 20000);
      token.renderUrl = URL.createObjectURL(token.blob); token.blob = null;
      state.image.src = token.renderUrl;
      (function(s, t) {
        s.image.decode().then(function() {
          if (!alive(s, t)) return;
          if (!s.image.naturalHeight) { fail(s, t, 'EncodingError'); return; }
          // Keep the URL through the first rendered frame; decoded pixels remain on the image.
          requestAnimationFrame(function() { requestAnimationFrame(function() { loaded(s, t); }); });
        }).catch(function() { fail(s, t, 'EncodingError'); });
      })(state, token);
    }
  }
  async function transport(state, token, source) {
    try {
      token.url = new URL(source, location.origin).href;
      var response = await fetch(token.url, {signal: token.controller.signal});
      if (!alive(state, token)) return;
      token.status = response.status; token.mime = (response.headers.get('Content-Type') || '').split(';')[0].toLowerCase();
      token.expected = Number(response.headers.get('Content-Length')) || 0;
      if (!response.ok) { fail(state, token, 'HTTPError'); return; }
      if (token.mime === 'text/html') { fail(state, token, 'AuthError'); return; }
      token.phase = 'body'; token.progress = Date.now(); watch(state, token, 45000);
      token.chunks = [];
      if (!response.body || !response.body.getReader) throw new TypeError('Readable image response required');
      token.reader = response.body.getReader();
      while (true) {
        var chunk = await token.reader.read();
        if (!alive(state, token)) return;
        if (chunk.done) break;
        if (chunk.value.byteLength) { token.received += chunk.value.byteLength; token.chunks.push(chunk.value); token.progress = Date.now(); watch(state, token, 45000); }
      }
      clearTimeout(token.watchdog);
      if (token.expected && !response.headers.get('Content-Encoding') && token.expected !== token.received) { fail(state, token, 'LengthMismatch'); return; }
      token.blob = new Blob(token.chunks, {type: token.mime}); token.chunks = null;
      token.phase = 'decode'; decodeQueue.push({state: state, token: token}); drainDecode();
    } catch (error) { if (alive(state, token)) fail(state, token, 'TypeError'); }
  }
  function drain() {
    if (suspended || batching || navigator.onLine === false) return;
    while (active < (allRequested ? 6 : 4) && queue.length) {
      queue.sort(function(a, b) { return distance(a.image) - distance(b.image); });
      var state = queue.shift(); state.queued = false;
      var image = state.image, source = image.getAttribute('data-src') || image.getAttribute('data-original');
      if (!source || state.hard || image.dataset.imageState === 'loaded' || image.isConnected === false) continue;
      var token = {controller: new AbortController(), phase: 'headers', started: Date.now(), progress: Date.now(), received: 0, finished: false};
      state.token = token; state.loading = true; state.attempts++; active++; image.dataset.imageState = 'loading';
      watch(state, token, 45000); transport(state, token, source);
    }
  }
  function load(image, retry) {
    if (!image) return;
    var state = bind(image); image = state.image;
    if (state.loading || state.queued || image.dataset.imageState === 'loaded') return;
    if (!retry && state.retryTimer) return;
    if (retry) { state.hard = false; state.attempts = state.decodeFailures = 0; }
    if (state.hard || (!allRequested && !retry && state.attempts >= 3)) return;
    if (!(image.getAttribute('data-src') || image.getAttribute('data-original'))) return;
    clearTimeout(state.retryTimer); state.retryTimer = null;
    state.queued = true; image.dataset.imageState = 'queued'; queue.push(state); drain();
  }
  var observer = new IntersectionObserver(function(entries) {
    batching = true;
    entries.forEach(function(entry) {
      if (!entry.isIntersecting) return;
      var image = entry.target.matches('img') ? entry.target : entry.target.querySelector('.page-img');
      if (typeof readerMode !== 'undefined' && readerMode === 'double' && entry.target.dataset.doubleGroup !== undefined) {
        var group = doubleGroups[Number(entry.target.dataset.doubleGroup)];
        if (group) { group.pages.forEach(function(index) { if (pages[index]) load(pages[index].querySelector('.page-img')); }); return; }
      }
      load(image);
    }); batching = false; drain();
  }, {rootMargin: (mobile ? '160px' : '600px') + ' 0px'});
  function observe(image) {
    if (!image) return; image = bind(image).image;
    if (suspended || observed.has(image) || image.dataset.imageState === 'loaded') return;
    observed.add(image); observer.observe(image.closest('.scramble-page') || image);
  }
  function scan(root) {
    (root || document).querySelectorAll('img.lazyload, img[data-image-state="error"]').forEach(function(image) { observe(image); if (allRequested) load(image); });
    updateAll();
  }
  function loadAll(root) {
    allRequested = true; allNotified = false; batching = true;
    (root || document).querySelectorAll('.page-img').forEach(function(image) { load(image, true); });
    batching = false; drain(); updateAll();
  }
  function pause() {
    suspended = true; observer.disconnect(); queue = [];
    known.forEach(function(state) {
      clearTimeout(state.retryTimer); state.retryTimer = null; state.queued = false;
      var token = state.token;
      if (token && alive(state, token)) {
        token.controller.abort(); if (token.reader) token.reader.cancel().catch(function() {});
        release(state, token); state.attempts = Math.max(0, state.attempts - 1);
        if (token.phase === 'decode') replacePendingImage(state);
        state.image.dataset.imageState = 'idle';
      } else if (state.image.dataset.imageState === 'queued') state.image.dataset.imageState = 'idle';
    }); decodeQueue = [];
  }
  function resume() {
    suspended = document.visibilityState === 'hidden'; if (suspended) return;
    observed = new WeakSet(); batching = true; scan(document);
    known.forEach(function(state) { if (!state.hard && state.image.dataset.imageState !== 'loaded' && (allRequested || distance(state.image) === 0)) load(state.image); });
    batching = false; drain();
  }
  window.JmvImageLoader = {load: load, loadAll: loadAll, observe: observe, scan: scan, currentImage: currentImage};
  window.addEventListener('scroll', drain, {passive: true});
  window.addEventListener('pagehide', pause);
  window.addEventListener('pageshow', function(event) { if (event.persisted) resume(); });
  window.addEventListener('online', resume);
  window.addEventListener('offline', pause);
  document.addEventListener('visibilitychange', function() { if (document.visibilityState === 'hidden') pause(); else resume(); });
})();
