(function () {
  'use strict';
  var config = { enabled: false, scopes: {} }, entries = {}, pending = {}, participating = false;
  var applying = false, operation = Promise.resolve(), status = '正在连接', storageKey = null, localBookmarks = [], lastApplied = '', conflictNotice = false;
  async function acquire() {
    var previous = operation, release;
    operation = new Promise(function(resolve) { release = resolve; });
    await previous;
    return release;
  }
  var preferenceNames = ['readerMode', 'readingDirection', 'doubleWidthScale', 'eyeCare', 'headerHidden', 'progressHidden', 'autoNext'];
  function canonicalPath(path) {
    var value = String(path || '').replace(/\\/g, '/');
    var windows = /^[a-z]:\//i.test(value) || /^\/\/[^/]+\/[^/]+/.test(value);
    var drive = /^[a-z]:\//i.test(value) ? value.slice(0, 3) : '';
    var unc = !drive && windows ? value.match(/^\/\/[^/]+\/[^/]+/)[0] : '';
    var root = drive || unc || (value.charAt(0) === '/' ? '/' : '');
    var remainder = value.slice(root.length), parts = [];
    remainder.split('/').forEach(function(part) {
      if (!part || part === '.') return;
      if (part === '..') { if (parts.length) parts.pop(); return; }
      parts.push(part);
    });
    var normalized = root + (unc && (parts.length || remainder) ? '/' : '') + parts.join('/');
    return windows ? normalized.toLowerCase() : normalized;
  }
  function scope(key) { var prefix = key.split(':')[0]; return { bookmark: 'bookmarks', progress: 'progress', sequence: 'sequence' }[prefix] || (prefix === 'preference' ? key.slice(11) : ''); }
  function allows(name) { return participating && config.enabled && config.scopes[name] === true; }
  function signal(extra) {
    window.dispatchEvent(new CustomEvent('jmv:sync-status', { detail: Object.assign({ status: status, config: config, participating: participating, pending: Object.keys(pending).length }, extra || {}) }));
  }
  function persist() {
    if (!storageKey) return;
    try { localStorage.setItem(storageKey, JSON.stringify({ participating: participating, entries: entries, pending: pending, localBookmarks: localBookmarks })); } catch (error) { status = '本机存储空间不足'; }
  }
  async function request(url, options) {
    var controller = typeof AbortController === 'function' ? new AbortController() : null;
    var timeout = controller ? window.setTimeout(function() { controller.abort(); }, 10000) : null;
    try {
      var response = await fetch(url, Object.assign({ headers: { 'Content-Type': 'application/json' }, cache: 'no-store', signal: controller ? controller.signal : undefined }, options || {}));
      var data = await response.json();
      if (!response.ok) { var error = new Error(data.error || '同步请求失败'); error.conflict = response.status === 409; throw error; }
      return data;
    } finally { if (timeout !== null) window.clearTimeout(timeout); }
  }
  function apply() {
    applying = true;
    try {
      if (allows('bookmarks')) {
        var effective = Object.assign({}, entries, pending);
        var bookmarks = Object.keys(effective).filter(function(key) { return key.indexOf('bookmark:') === 0 && effective[key].value; }).map(function(key) { return effective[key].value; });
        localStorage.setItem('plugin_jm_bookmarks', JSON.stringify(bookmarks));
        if (typeof window.renderBookmarks === 'function') window.renderBookmarks();
      }
      preferenceNames.forEach(function(name) {
        var record = pending['preference:' + name] || entries['preference:' + name];
        if (!allows(name) || !record || !window.JmvPrefs) return;
        // 阅读过程中只更新缓存，避免跨设备操作突然改变正在看的画面。
        if (window.location.pathname === '/jm_view') {
          var def = window.JmvPrefs.definitions[name];
          if (record.value === null) localStorage.removeItem(def.key);
          else localStorage.setItem(def.key, def.type === 'bool' ? (record.value ? '1' : '0') : String(record.value));
        } else if (record.value === null) window.JmvPrefs.remove(name);
        else window.JmvPrefs.set(name, record.value);
      });
      window.dispatchEvent(new CustomEvent('jmv:sync-applied', { detail: { entries: Object.assign({}, entries, pending), scopes: config.scopes, enabled: participating && config.enabled } }));
    } finally { applying = false; }
  }
  async function refresh() {
    var release = await acquire();
    try {
      config = await request('/api/sync/config');
      var nextKey = 'jmv-sync:' + config.server_id;
      if (storageKey !== nextKey) {
        storageKey = nextKey;
        var saved = {};
        try { saved = JSON.parse(localStorage.getItem(storageKey) || '{}'); } catch (error) {}
        if (!saved || typeof saved !== 'object' || Array.isArray(saved)) saved = {};
        participating = typeof saved.participating === 'boolean' ? saved.participating : true;
        entries = saved.entries || {}; pending = saved.pending || {}; localBookmarks = Array.isArray(saved.localBookmarks) ? saved.localBookmarks : [];
        if (typeof saved.participating !== 'boolean') {
          // Keep the pre-sync bookmarks recoverable when a new browser adopts server state.
          try { localBookmarks = JSON.parse(localStorage.getItem('plugin_jm_bookmarks') || '[]'); } catch (error) { localBookmarks = []; }
          if (!Array.isArray(localBookmarks)) localBookmarks = [];
          persist();
        }
      }
      Object.keys(pending).forEach(function(key) { if (!allows(scope(key))) delete pending[key]; });
      if (participating && config.enabled) {
        var snapshot = await request('/api/sync/state');
        entries = snapshot.entries || {};
        // 不把陈旧离线操作自动重放为新的写入，防止复活已删除的记录。
        var conflicted = false;
        Object.keys(pending).forEach(function(key) {
          if ((entries[key] ? entries[key].revision : 0) !== pending[key].base_revision) { delete pending[key]; conflicted = true; }
        });
        var fingerprint = JSON.stringify([entries, pending, config.scopes]);
        if (fingerprint !== lastApplied) { apply(); lastApplied = fingerprint; }
        conflictNotice = conflictNotice || conflicted;
        status = conflictNotice ? '其他设备已更新，已采用服务器数据，请检查后重新操作' : Object.keys(pending).length ? '有修改待同步，请重试' : '已同步';
      } else status = participating ? '等待服务器开启同步' : '此浏览器未参与同步';
      persist();
    } catch (error) { status = Object.keys(pending).length ? '待同步：连接失败，可重试' : '连接失败，可重试'; }
    finally { release(); signal(); }
  }
  async function flush() {
    var release = await acquire();
    if (!participating || !config.enabled) { release(); return; }
    var changes = Object.keys(pending).filter(function(key) { return allows(scope(key)); }).slice(0, 100).map(function(key) { return Object.assign({ key: key }, pending[key]); });
    if (!changes.length) { release(); return; }
    var succeeded = false;
    try {
      var accepted = await request('/api/sync/state', { method: 'POST', body: JSON.stringify({ changes: changes }) });
      changes.forEach(function(change) {
        if (!pending[change.key]) return;
        if (JSON.stringify(pending[change.key].value) === JSON.stringify(change.value)) delete pending[change.key];
        else if (accepted.entries && accepted.entries[change.key]) pending[change.key].base_revision = accepted.entries[change.key].revision;
      });
      status = '已同步';
      succeeded = true;
    } catch (error) {
      if (error.conflict) { changes.forEach(function(change) { delete pending[change.key]; }); conflictNotice = true; status = '其他设备已更新，已采用服务器数据'; }
      else status = '待同步：连接失败，可重试';
    } finally { release(); persist(); signal(); }
    await refresh();
    if (succeeded && Object.keys(pending).length) window.setTimeout(flush, 180);
  }
  function setRecord(key, value) {
    if (applying || !allows(scope(key))) return;
    conflictNotice = false;
    if (!pending[key] && Object.keys(pending).length >= 1000) { status = '待同步记录已满，请先重试'; signal(); return; }
    pending[key] = { value: value, base_revision: pending[key] ? pending[key].base_revision : entries[key] ? entries[key].revision : 0 };
    persist(); signal(); window.clearTimeout(setRecord.timer); setRecord.timer = window.setTimeout(flush, 180);
  }
  async function setEnabled(value, initialize) {
    if (value) window.dispatchEvent(new CustomEvent('jmv:sync-before-enable'));
    var initialBookmarks = [];
    try { initialBookmarks = JSON.parse(localStorage.getItem('plugin_jm_bookmarks') || '[]'); } catch (error) {}
    if (value && !participating && (initialBookmarks.length || !localBookmarks.length)) localBookmarks = initialBookmarks;
    participating = Boolean(value); lastApplied = ''; if (!participating) pending = {};
    persist(); await refresh();
    if (participating && config.enabled && initialize) {
      mergeBookmarks(initialBookmarks);
      preferenceNames.forEach(function(name) { if (allows(name) && !entries['preference:' + name]) setRecord('preference:' + name, window.JmvPrefs.get(name)); });
      window.dispatchEvent(new CustomEvent('jmv:sync-initialize', { detail: { scopes: config.scopes } }));
    }
    signal();
  }
  function mergeBookmarks(source) {
    if (!allows('bookmarks')) return;
    var bookmarks = source;
    if (!bookmarks) {
      bookmarks = localBookmarks.slice();
      try { bookmarks = bookmarks.concat(JSON.parse(localStorage.getItem('plugin_jm_bookmarks') || '[]')); } catch (error) {}
    }
    bookmarks.forEach(function(item) { var key = 'bookmark:' + canonicalPath(item.path); if (!entries[key]) setRecord(key, { path: item.path, timestamp: item.timestamp }); });
  }
  window.addEventListener('jmv:preference-change', function(event) { var name = event.detail.name; if (preferenceNames.indexOf(name) >= 0) setRecord('preference:' + name, event.detail.value); });
  window.addEventListener('focus', refresh);
  document.addEventListener('visibilitychange', function() { if (!document.hidden) refresh(); });
  window.addEventListener('storage', function(event) { if (event.key === storageKey) { storageKey = null; refresh(); } });
  window.setInterval(function() { if (participating && !document.hidden) refresh(); }, 5000);
  window.JmvSync = {
    canonicalPath: canonicalPath, setRecord: setRecord,
    getRecord: function(key) { var record = pending[key] || entries[key]; return allows(scope(key)) && record ? record.value : undefined; },
    isEnabled: function() { return participating && config.enabled; }, allows: allows,
    refresh: refresh, retry: async function() { await refresh(); await flush(); }, setEnabled: setEnabled,
    mergeBookmarks: mergeBookmarks, getStatus: function() { return { config: config, participating: participating, status: status, entries: entries }; },
    clearScope: function(name) { Object.keys(Object.assign({}, entries, pending)).forEach(function(key) { if (scope(key) === name) setRecord(key, null); }); },
    saveConfig: async function(value) { await request('/api/sync/config', { method: 'PUT', body: JSON.stringify(Object.assign({}, value, { base_revision: config.revision })) }); await refresh(); }
  };
  window.JmvSync.ready = refresh();
})();
