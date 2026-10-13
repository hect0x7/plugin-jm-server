(function() {
  function remember(kind, album, value) {
    if (!album || album === 'favorites') return;
    var key = kind + ':' + JmvSync.canonicalPath(album);
    try { if (value === null) localStorage.removeItem('jmv-sync-' + key); else localStorage.setItem('jmv-sync-' + key, JSON.stringify(value)); } catch (error) {}
    JmvSync.setRecord(key, value);
  }
  function imagePath(image) {
    var source = image && (image.getAttribute('data-original') || image.getAttribute('data-src'));
    return source ? new URL(source, location.origin).searchParams.get('path') : null;
  }
  window.JmvReaderMemory = {
    imagePath: imagePath,
    progress: function(album, image) { var path = imagePath(image); if (path) remember('progress', album, {image: path}); },
    sequence: function(album, items) { remember('sequence', album, items === null ? null : {items: items}); },
    get: function(kind, album) { return JmvSync.getRecord(kind + ':' + JmvSync.canonicalPath(album)); }
  };
  window.addEventListener('jmv:sync-before-enable', function() {
    var backup = {};
    for (var i = 0; i < localStorage.length; i++) {
      var key = localStorage.key(i);
      if (key.indexOf('jmv-sync-progress:') === 0 || key.indexOf('jmv-sync-sequence:') === 0) backup[key] = localStorage.getItem(key);
    }
    try { localStorage.setItem('jmv-reader-memory-backup', JSON.stringify(backup)); } catch (error) {}
  });
  window.addEventListener('jmv:sync-initialize', function() {
    var backup = {};
    try { backup = JSON.parse(localStorage.getItem('jmv-reader-memory-backup') || '{}'); } catch (error) {}
    Object.keys(backup).forEach(function(key) {
      var recordKey = key.slice('jmv-sync-'.length);
      if (JmvSync.getRecord(recordKey) !== undefined) return;
      try { JmvSync.setRecord(recordKey, JSON.parse(backup[key])); } catch (error) {}
    });
  });
  window.addEventListener('jmv:sync-applied', function(event) {
    if (!event.detail.enabled) return;
    Object.keys(event.detail.entries).forEach(function(key) {
      if (key.indexOf('progress:') !== 0 && key.indexOf('sequence:') !== 0) return;
      var scope = key.indexOf('progress:') === 0 ? 'progress' : 'sequence';
      if (!event.detail.scopes[scope]) return;
      var value = event.detail.entries[key].value;
      try { if (value === null) localStorage.removeItem('jmv-sync-' + key); else localStorage.setItem('jmv-sync-' + key, JSON.stringify(value)); } catch (error) {}
    });
  });
})();
