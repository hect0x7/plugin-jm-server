"""Sync policy, optimistic concurrency and persistence use isolated data only."""
import json
import pytest
from flask import Flask

from jm_view_server.routes.sync import SyncRoutesMixin
from jm_view_server.sync import DEFAULT_SCOPES, SyncManager, canonical_path


@pytest.fixture
def server(tmp_path):
    class Server(SyncRoutesMixin):
        authorized = True

        def verify(self):
            return self.authorized

    instance = Server()
    instance.sync_manager = SyncManager(tmp_path / 'sync.json')
    instance.app = Flask(__name__)
    instance.app.add_url_rule('/api/sync/config', view_func=instance.api_sync_config, methods=['GET', 'PUT'])
    instance.app.add_url_rule('/api/sync/state', view_func=instance.api_sync_state, methods=['GET', 'POST'])
    return instance


def enable(client, **scopes):
    response = client.put('/api/sync/config', json={'enabled': True, 'scopes': scopes})
    assert response.status_code == 200
    return response.json


def change(path, base=0, value=None, kind='progress'):
    return {'key': f'{kind}:{path}', 'value': value or {'image': str(path / 'page.png')}, 'base_revision': base}


def post(client, *changes):
    return client.post('/api/sync/state', json={'changes': list(changes)})


def test_defaults_identity_and_config_permissions(server):
    client = server.app.test_client()
    result = client.get('/api/sync/config').json
    assert result['enabled'] is True and result['scopes'] == DEFAULT_SCOPES
    assert result['editable'] is True and result['revision'] == 0
    assert client.get('/api/sync/config').json['server_id'] == result['server_id']
    remote = {'REMOTE_ADDR': '192.0.2.20'}
    assert client.get('/api/sync/config', environ_overrides=remote).json['editable'] is False
    blocked = client.put('/api/sync/config', json={'enabled': True}, environ_overrides=remote,
                         headers={'X-Forwarded-For': '127.0.0.1'})
    assert blocked.status_code == 403
    assert client.get('/api/sync/config').json['enabled'] is True
    assert client.get('/api/sync/config', environ_overrides={'REMOTE_ADDR': '::1'}).json['editable'] is True


@pytest.mark.parametrize('endpoint,method', [('/api/sync/config', 'get'), ('/api/sync/config', 'put'),
                                           ('/api/sync/state', 'get'), ('/api/sync/state', 'post')])
def test_authentication(server, endpoint, method):
    server.authorized = False
    assert getattr(server.app.test_client(), method)(endpoint, json={}).status_code == 401
    assert not server.sync_manager.data_file.exists()


def test_disabled_and_scope_restrictions(server, tmp_path):
    client = server.app.test_client()
    assert client.put('/api/sync/config', json={'enabled': False}).status_code == 200
    assert post(client, change(tmp_path)).status_code == 403
    enable(client, progress=False)
    assert post(client, change(tmp_path)).status_code == 403
    forbidden = {'key': 'preference:readerMode', 'value': 'double', 'base_revision': 0}
    assert post(client, forbidden).status_code == 403
    assert client.get('/api/sync/state').json['entries'] == {}


def test_saved_disabled_policy_and_scopes_survive_new_defaults(tmp_path):
    data_file = tmp_path / 'sync.json'
    manager = SyncManager(data_file)
    original = manager.get_config()
    scopes = dict(original['scopes'], progress=False, readingDirection=True)
    manager.set_config({'enabled': False, 'scopes': scopes})
    restored = SyncManager(data_file).get_config()
    assert restored['enabled'] is False
    assert restored['scopes'] == scopes


def test_patch_round_trip_and_filtering(server, tmp_path):
    client = server.app.test_client()
    enable(client, readerMode=True)
    a = change(tmp_path)
    mode = {'key': 'preference:readerMode', 'value': 'double', 'base_revision': 0}
    result = post(client, a, mode)
    assert result.status_code == 200
    revision = result.json['revision']
    key = f'progress:{canonical_path(str(tmp_path))}'
    assert result.json['entries'][key]['value']['image'] == canonical_path(str(tmp_path / 'page.png'))
    assert client.get('/api/sync/state').json == result.json
    assert post(client, change(tmp_path, revision, {'image': str(tmp_path / 'next.png')})).status_code == 200
    enable(client, readerMode=False)
    assert 'preference:readerMode' not in client.get('/api/sync/state').json['entries']
    enable(client, readerMode=True)
    assert client.get('/api/sync/state').json['entries']['preference:readerMode']['value'] == 'double'


def test_conflict_is_atomic_and_tombstones_prevent_resurrection(server, tmp_path):
    client = server.app.test_client()
    enable(client)
    result = post(client, change(tmp_path)).json
    current = result['revision']
    before = server.sync_manager.data_file.read_bytes()
    conflict = post(client, change(tmp_path), change(tmp_path / 'other'))
    assert conflict.status_code == 409 and conflict.json['conflicts'][0]['revision'] == current
    assert server.sync_manager.data_file.read_bytes() == before
    deleted = post(client, {'key': f'progress:{tmp_path}', 'value': None, 'base_revision': current})
    assert deleted.status_code == 200
    key = f'progress:{canonical_path(str(tmp_path))}'
    assert deleted.json['entries'][key]['value'] is None
    assert post(client, change(tmp_path)).status_code == 409


def test_config_revision_conflict(server):
    client = server.app.test_client()
    enable(client, progress=False)
    assert client.put('/api/sync/config', json={'enabled': False, 'base_revision': 0}).status_code == 409
    assert client.get('/api/sync/config').json['enabled'] is True


@pytest.mark.parametrize('body', [{'enabled': 1}, {'scopes': {'unknown': True}}, {'scopes': {'progress': 'true'}},
                                 {'base_revision': True}, {'unexpected': 'value'}])
def test_invalid_config(server, body):
    assert server.app.test_client().put('/api/sync/config', json=body).status_code == 400


@pytest.mark.parametrize('changes', [[], [None], [{'key': 'bogus:x', 'value': None, 'base_revision': 0}],
                                    [{'key': 'preference:doubleWidthScale', 'value': True, 'base_revision': 0}],
                                    [{'key': 'preference:readerMode', 'value': [], 'base_revision': 0}],
                                    [{'key': 'progress:relative', 'value': None, 'base_revision': 0}]])
def test_invalid_changes(server, changes):
    client = server.app.test_client()
    enable(client)
    assert client.post('/api/sync/state', json={'changes': changes}).status_code == 400


def test_duplicate_canonical_keys_and_limits(server, tmp_path):
    client = server.app.test_client()
    enable(client)
    same = change(tmp_path / 'child' / '..')
    assert post(client, change(tmp_path), same).status_code == 400
    assert post(client, *[change(tmp_path / str(i)) for i in range(101)]).status_code == 400
    response = client.post('/api/sync/state', data=b' ' * (1024 * 1024 + 1), content_type='application/json')
    assert response.status_code == 400


def test_bookmarks_sequence_and_preferences(server, tmp_path):
    client = server.app.test_client()
    enable(client, doubleWidthScale=True, eyeCare=True)
    bookmark = change(tmp_path, kind='bookmark', value={'path': str(tmp_path), 'timestamp': '2026-01-01T00:00:00Z'})
    sequence = change(tmp_path, kind='sequence', value={'items': [
        {'type': 'page', 'path': str(tmp_path / 'page.png')}, {'type': 'blank', 'id': 'blank-1'}]})
    assert post(client, bookmark, sequence,
                {'key': 'preference:doubleWidthScale', 'value': 98, 'base_revision': 0},
                {'key': 'preference:eyeCare', 'value': True, 'base_revision': 0}).status_code == 200
    invalid = change(tmp_path / 'invalid', kind='sequence', value={'items': [
        {'type': 'blank', 'id': 'same'}, {'type': 'blank', 'id': 'same'}]})
    assert post(client, invalid).status_code == 400


@pytest.mark.parametrize('content', ['{broken', '{"enabled":false}', '{"server_id":null}'])
def test_corrupt_file_preserved(server, content):
    server.sync_manager.data_file.write_text(content, encoding='utf-8')
    client = server.app.test_client()
    assert client.get('/api/sync/config').status_code == 500
    assert client.put('/api/sync/config', json={'enabled': True}).status_code == 500
    assert server.sync_manager.data_file.read_text(encoding='utf-8') == content


def test_write_failure_keeps_previous_state_and_cleans_temporary_file(server, monkeypatch, tmp_path):
    client = server.app.test_client()
    enable(client)
    original = server.sync_manager.data_file.read_bytes()
    def fail(*args):
        raise OSError('simulated failure')
    monkeypatch.setattr('jm_view_server.sync.os.replace', fail)
    assert post(client, change(tmp_path)).status_code == 500
    assert client.put('/api/sync/config', json={'enabled': False}).status_code == 500
    assert server.sync_manager.data_file.read_bytes() == original
    assert list(tmp_path.iterdir()) == [server.sync_manager.data_file]


def test_saved_data_revision_validation(server):
    client = server.app.test_client()
    enable(client)
    data = json.loads(server.sync_manager.data_file.read_text(encoding='utf-8'))
    data['revision'] = True
    server.sync_manager.data_file.write_text(json.dumps(data), encoding='utf-8')
    assert client.get('/api/sync/state').status_code == 500


def test_reading_updates_do_not_conflict_with_policy_editor(server, tmp_path):
    client = server.app.test_client()
    config = enable(client)
    base = 0
    for i in range(3):
        result = post(client, change(tmp_path, base, {'image': str(tmp_path / f'{i}.png')}))
        assert result.status_code == 200
        base = result.json['revision']
    assert client.get('/api/sync/config').json['revision'] == config['revision']
    saved = client.put('/api/sync/config', json={
        'base_revision': config['revision'], 'scopes': {'readerMode': True}})
    assert saved.status_code == 200
    assert saved.json['revision'] == config['revision'] + 1
    assert client.get('/api/sync/state').json['revision'] == base + 1
    stale_editor = client.put('/api/sync/config', json={
        'base_revision': config['revision'], 'scopes': {'sequence': False}})
    assert stale_editor.status_code == 409
    assert stale_editor.json['conflicts'] == [{'key': 'config', 'revision': saved.json['revision']}]
    assert client.get('/api/sync/config').json['scopes']['sequence'] is True


def make_legacy_sync_file(server, tmp_path):
    client = server.app.test_client()
    enable(client)
    assert post(client, change(tmp_path)).status_code == 200
    post(client, {'key': f'progress:{tmp_path / "deleted"}', 'value': None, 'base_revision': 0})
    data = json.loads(server.sync_manager.data_file.read_text(encoding='utf-8'))
    data.pop('config_revision')
    server.sync_manager.data_file.write_text(json.dumps(data), encoding='utf-8')
    return data


def test_legacy_migration_keeps_identity_entries_and_tombstones(server, tmp_path):
    legacy = make_legacy_sync_file(server, tmp_path)
    client = server.app.test_client()
    config = client.get('/api/sync/config')
    assert config.status_code == 200 and config.json['server_id'] == legacy['server_id']
    assert config.json['revision'] == legacy['revision']
    state = client.get('/api/sync/state').json
    assert state['entries'] == legacy['entries'] and state['revision'] == legacy['revision']
    saved = json.loads(server.sync_manager.data_file.read_text(encoding='utf-8'))
    assert saved == {**legacy, 'config_revision': legacy['revision']}
    response = client.put('/api/sync/config', json={
        'base_revision': config.json['revision'], 'scopes': {'readerMode': True}})
    assert response.status_code == 200


def test_failed_migration_keeps_legacy_file(server, tmp_path, monkeypatch):
    make_legacy_sync_file(server, tmp_path)
    previous = server.sync_manager.data_file.read_bytes()
    def fail(*args):
        raise OSError('simulated migration failure')
    monkeypatch.setattr('jm_view_server.sync.os.replace', fail)
    assert server.app.test_client().get('/api/sync/config').status_code == 500
    assert server.sync_manager.data_file.read_bytes() == previous
    assert list(tmp_path.iterdir()) == [server.sync_manager.data_file]


@pytest.mark.parametrize('version', [True, -1, 100, '1'])
def test_invalid_policy_revision_is_not_migrated(server, version):
    client = server.app.test_client()
    enable(client)
    data = json.loads(server.sync_manager.data_file.read_text(encoding='utf-8'))
    data['config_revision'] = version
    original = json.dumps(data)
    server.sync_manager.data_file.write_text(original, encoding='utf-8')
    assert client.get('/api/sync/config').status_code == 500
    assert server.sync_manager.data_file.read_text(encoding='utf-8') == original
