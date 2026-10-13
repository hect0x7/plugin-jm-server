(function() {
  if (readerConfig.favorites) {
    document.getElementById('tOpenFolder').style.display = 'none';
    document.getElementById('tAutoNext').style.display = 'none';
  }
  function imagePath(image) {
    var source = image && (image.getAttribute('data-original') || image.getAttribute('data-src'));
    return source ? new URL(source, location.origin).searchParams.get('path') : null;
  }
  async function read(image) {
    var path = imagePath(image);
    if (!path) throw new Error('无法识别图片');
    var response = await fetch('/api/favorites', {cache: 'no-store'});
    if (!response.ok) throw new Error('无法读取收藏状态');
    var data = await response.json();
    return {path: path, favorite: data.images.some(function(item) { return JmvSync.canonicalPath(item.path) === JmvSync.canonicalPath(path); })};
  }
  async function set(image, favorite) {
    var path = imagePath(image);
    if (!path) throw new Error('无法识别图片');
    var response = await fetch('/api/favorites', {
      method: favorite ? 'PUT' : 'DELETE', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: path})
    });
    var data = await response.json();
    if (!response.ok) throw new Error(data.error || '收藏操作失败，请重试');
    return data.favorite;
  }
  window.JmvFavorites = {read: read, set: set, imagePath: imagePath};
})();
