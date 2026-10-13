import io
import subprocess
import threading

import pytest
from PIL import Image

from jm_view_server.app import JmServer
from jm_view_server.thumbnail import SystemVideoThumbnailCache, ThumbnailBusyError
from jm_view_server import windows_thumbnail


@pytest.fixture
def video_server(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))
    video = tmp_path / 'sample.MP4'
    video.write_bytes(b'generated invalid video')
    server = JmServer(str(tmp_path), '')
    server.register_routes()
    return server, video


def png_bytes():
    output = io.BytesIO()
    Image.new('RGB', (16, 9), 'blue').save(output, format='PNG')
    return output.getvalue()


def test_video_metadata_stays_file_and_does_not_enter_reader(video_server):
    server, video = video_server
    info = server.file_manager.build_one_path_info(str(video))
    assert info['type'] == 'file'
    assert info['jm_view'] is False
    assert info['first_img_url']['thumbnail_source'] == 'system'
    assert info['first_img_url']['data_thumb'].endswith('&source=system')
    assert 'data_original' not in info['first_img_url']
    assert server.file_manager.get_jm_view_images(str(video.parent)) == []


def test_system_failure_and_image_source_never_send_video(video_server, monkeypatch):
    from jm_view_server.thumbnail import system_video_thumbnail_cache
    server, video = video_server
    monkeypatch.setattr(system_video_thumbnail_cache, 'get_thumbnail', lambda *a, **k: None)
    client = server.app.test_client()
    for source in ('system', 'image'):
        response = client.get('/api/thumb', query_string={'path': str(video), 'source': source})
        assert response.status_code == 404
        assert b'generated invalid video' not in response.data
    server.password = 'test-password'
    assert client.get('/api/thumb', query_string={'path': str(video), 'source': 'system'}).status_code == 403


def test_system_png_and_etag_and_image_thumbnails(video_server, monkeypatch):
    from jm_view_server.thumbnail import system_video_thumbnail_cache
    server, video = video_server
    data = png_bytes()
    monkeypatch.setattr(system_video_thumbnail_cache, 'get_thumbnail',
                        lambda *a, **k: (data, 'image/png', 1, '"test-etag"'))
    client = server.app.test_client()
    query = {'path': str(video), 'source': 'system'}
    response = client.get('/api/thumb', query_string=query)
    assert response.status_code == 200
    assert response.mimetype == 'image/png' and response.data == data
    assert client.get('/api/thumb', query_string=query,
                      headers={'If-None-Match': '"test-etag"'}).status_code == 304
    image = video.parent / 'sample.png'
    image.write_bytes(data)
    assert client.get('/api/thumb', query_string={'path': str(image)}).mimetype.startswith('image/')
    assert client.get('/api/thumb', query_string={'path': str(image), 'source': 'system'}).status_code == 404
    assert client.get('/api/thumb', query_string={'path': str(image), 'source': 'invalid'}).status_code == 400


def test_cache_is_bounded_invalidates_changed_files_and_clamps_size(tmp_path, monkeypatch):
    data = png_bytes()
    calls = []
    monkeypatch.setattr(windows_thumbnail, 'extract_thumbnail',
                        lambda *args: calls.append(args) or data)
    cache = SystemVideoThumbnailCache(max_entries=1)
    a, b = tmp_path / 'a.mp4', tmp_path / 'b.mkv'
    a.write_bytes(b'a')
    b.write_bytes(b'b')
    first = cache.get_thumbnail(str(a), 99999, -1)
    assert calls[-1][1:] == (512, 1)
    assert cache.get_thumbnail(str(a), 99999, -1) == first
    assert len(calls) == 1
    a.write_bytes(b'changed')
    assert cache.get_thumbnail(str(a), 99999, -1)[3] != first[3]
    cache.get_thumbnail(str(b))
    assert len(cache._cache) == 1
    cache.clear()
    assert not cache._cache and not cache._failures


def test_negative_cache_is_short_lived_and_bounded(tmp_path, monkeypatch):
    calls = []
    clock = [100]
    monkeypatch.setattr(windows_thumbnail, 'extract_thumbnail',
                        lambda *args: calls.append(args) or None)
    monkeypatch.setattr('jm_view_server.thumbnail.time.monotonic', lambda: clock[0])
    cache = SystemVideoThumbnailCache(max_entries=1)
    path = tmp_path / 'bad.mp4'
    path.write_bytes(b'bad')
    assert cache.get_thumbnail(str(path)) is None
    assert cache.get_thumbnail(str(path)) is None
    assert len(calls) == 1
    clock[0] += 31
    cache.get_thumbnail(str(path))
    assert len(calls) == 2
    second = tmp_path / 'second.mp4'
    second.write_bytes(b'bad')
    cache.get_thumbnail(str(second))
    assert len(cache._failures) == 1


def test_busy_is_not_negative_cached_and_api_allows_retry(video_server, monkeypatch):
    from jm_view_server.thumbnail import system_video_thumbnail_cache
    server, video = video_server
    cache = SystemVideoThumbnailCache()
    class BusyLock:
        def acquire(self, timeout):
            assert timeout == 6
            return False
    cache._extract_lock = BusyLock()
    with pytest.raises(ThumbnailBusyError):
        cache.get_thumbnail(str(video))
    assert not cache._failures
    cache._extract_lock = threading.Lock()
    monkeypatch.setattr(windows_thumbnail, 'extract_thumbnail', lambda *a: png_bytes())
    assert cache.get_thumbnail(str(video))[1] == 'image/png'
    def busy(*args, **kwargs):
        raise ThumbnailBusyError()
    monkeypatch.setattr(system_video_thumbnail_cache, 'get_thumbnail', busy)
    response = server.app.test_client().get('/api/thumb',
        query_string={'path': str(video), 'source': 'system'})
    assert response.status_code == 503
    assert response.headers['Retry-After'] == '1'
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.skipif(windows_thumbnail.os.name != 'nt', reason='Windows worker')
def test_worker_timeout_is_handled_without_shell_or_visible_window(monkeypatch):
    def run(command, **kwargs):
        assert command[1] == '-B'
        assert 'shell' not in kwargs
        assert kwargs['creationflags'] == subprocess.CREATE_NO_WINDOW
        assert kwargs['timeout'] == 6
        raise subprocess.TimeoutExpired(command, 6)
    monkeypatch.setattr(windows_thumbnail.subprocess, 'run', run)
    assert windows_thumbnail.extract_thumbnail('sample.mp4', 300, 400) is None
