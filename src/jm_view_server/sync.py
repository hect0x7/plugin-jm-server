"""Server-controlled, revisioned reading memory shared by participating browsers."""
import copy
import json
import math
import os
import tempfile
import threading
import uuid
from datetime import datetime
from pathlib import Path


DEFAULT_SCOPES = {
    'bookmarks': True, 'progress': True, 'sequence': True,
    'readerMode': False, 'readingDirection': False, 'doubleWidthScale': False,
    'eyeCare': False, 'headerHidden': False, 'progressHidden': False, 'autoNext': False,
}
MAX_BODY_BYTES = 1024 * 1024


class SyncDisabledError(PermissionError):
    pass


class SyncDataError(ValueError):
    pass


class SyncConflictError(ValueError):
    def __init__(self, conflicts):
        super().__init__('同步资料已更新，请重新获取后重试')
        self.conflicts = conflicts


def canonical_path(path):
    if (not isinstance(path, str) or not path or len(path) > 4096
            or '\x00' in path or not os.path.isabs(path)):
        raise ValueError('需要有效的服务器绝对路径')
    normalized = os.path.normcase(os.path.normpath(path))
    return normalized.replace('\\', '/') if os.name == 'nt' else normalized


def validate_entry(key, value):
    if not isinstance(key, str) or ':' not in key:
        raise ValueError('无效的同步资料键')
    kind, identity = key.split(':', 1)
    if kind == 'preference':
        if identity not in DEFAULT_SCOPES or identity in ('bookmarks', 'progress', 'sequence'):
            raise ValueError('不支持同步该设置')
        scope = identity
    elif kind in ('bookmark', 'progress', 'sequence'):
        identity = canonical_path(identity)
        scope = 'bookmarks' if kind == 'bookmark' else kind
    else:
        raise ValueError('不支持的同步资料类型')
    if value is None:
        return f'{kind}:{identity}', scope, None
    if kind == 'preference':
        if identity == 'readerMode':
            valid = isinstance(value, str) and value in ('scroll', 'single', 'double')
        elif identity == 'readingDirection':
            valid = isinstance(value, str) and value in ('ltr', 'rtl')
        elif identity == 'doubleWidthScale':
            valid = (type(value) in (int, float) and math.isfinite(value) and 50 <= value <= 100)
        else:
            valid = type(value) is bool
        if not valid:
            raise ValueError('无效的阅读设置值')
    else:
        fields = {'bookmark': {'path', 'timestamp'}, 'progress': {'image'}, 'sequence': {'items'}}[kind]
        if not isinstance(value, dict) or set(value) != fields:
            raise ValueError('无效的同步资料值')
        value = copy.deepcopy(value)
        if kind == 'bookmark':
            value['path'] = canonical_path(value['path'])
            if value['path'] != identity:
                raise ValueError('收藏目录与资料键不一致')
            stamp = value['timestamp']
            if not isinstance(stamp, str) or len(stamp) > 64:
                raise ValueError('无效的收藏时间')
            try:
                datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            except ValueError:
                raise ValueError('无效的收藏时间') from None
        elif kind == 'progress':
            value['image'] = canonical_path(value['image'])
        else:
            items = value['items']
            if not isinstance(items, list) or len(items) > 5000:
                raise ValueError('排序资料过大或无效')
            seen = set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError('无效的排序条目')
                if item.get('type') == 'page' and set(item) == {'type', 'path'}:
                    item['path'] = canonical_path(item['path'])
                    item_key = ('page', item['path'])
                elif item.get('type') == 'blank' and set(item) == {'type', 'id'}:
                    if not isinstance(item['id'], str) or not item['id'] or len(item['id']) > 128:
                        raise ValueError('无效的空白页标识')
                    item_key = ('blank', item['id'])
                else:
                    raise ValueError('无效的排序条目')
                if item_key in seen:
                    raise ValueError('排序包含重复条目')
                seen.add(item_key)
    return f'{kind}:{identity}', scope, value


class SyncManager:
    _locks = {}
    _locks_guard = threading.Lock()

    def __init__(self, data_file=None):
        self.data_file = Path(data_file) if data_file else Path.home() / '.jm_view_server' / 'sync.json'
        key = os.path.normcase(os.path.abspath(self.data_file))
        with self._locks_guard:
            self._lock = self._locks.setdefault(key, threading.Lock())

    def _load(self):
        try:
            with self.data_file.open(encoding='utf-8') as handle:
                data = json.load(handle)
        except FileNotFoundError:
            data = {'server_id': str(uuid.uuid4()), 'enabled': True,
                    'scopes': dict(DEFAULT_SCOPES), 'revision': 0, 'config_revision': 0, 'entries': {}}
            self._save(data)
            return data
        except (ValueError, UnicodeError):
            raise SyncDataError('同步资料损坏，请先检查资料文件') from None
        fields = {'server_id', 'enabled', 'scopes', 'revision', 'entries'}
        legacy = isinstance(data, dict) and set(data) == fields
        if (not isinstance(data, dict) or set(data) not in (fields, fields | {'config_revision'})
                or type(data['enabled']) is not bool or type(data['revision']) is not int
                or data['revision'] < 0 or not isinstance(data['scopes'], dict)
                or set(data['scopes']) != set(DEFAULT_SCOPES)
                or any(type(v) is not bool for v in data['scopes'].values())
                or not isinstance(data['entries'], dict)):
            raise SyncDataError('同步资料损坏，请先检查资料文件')
        if not legacy and (type(data['config_revision']) is not int
                           or not 0 <= data['config_revision'] <= data['revision']):
            raise SyncDataError('同步资料损坏，请先检查资料文件')
        try:
            if str(uuid.UUID(data['server_id'])) != data['server_id']:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            raise SyncDataError('同步资料损坏，请先检查资料文件') from None
        for key, entry in data['entries'].items():
            if (not isinstance(entry, dict) or set(entry) != {'value', 'revision'}
                    or type(entry['revision']) is not int or not 0 < entry['revision'] <= data['revision']):
                raise SyncDataError('同步资料损坏，请先检查资料文件')
            try:
                canonical, _, value = validate_entry(key, entry['value'])
            except ValueError:
                raise SyncDataError('同步资料损坏，请先检查资料文件') from None
            if canonical != key or value != entry['value']:
                raise SyncDataError('同步资料损坏，请先检查资料文件')
        if legacy:
            # Preserve the old version for any policy editor already open.
            # Validate every record before migrating; failures never overwrite it.
            data['config_revision'] = data['revision']
            self._save(data)
        return data

    def _save(self, data):
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        name = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.data_file.parent,
                                             delete=False) as handle:
                name = handle.name
                json.dump(data, handle, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(name, self.data_file)
        finally:
            if name and os.path.exists(name):
                os.unlink(name)

    @staticmethod
    def _snapshot(data):
        entries = {}
        if data['enabled']:
            for key, entry in data['entries'].items():
                _, scope, _ = validate_entry(key, None)
                if data['scopes'][scope]:
                    entries[key] = entry
        return copy.deepcopy({key: entries if key == 'entries' else value
                              for key, value in data.items() if key != 'config_revision'})

    @staticmethod
    def _config(data):
        return {**{key: data[key] for key in ('server_id', 'enabled', 'scopes')},
                'revision': data['config_revision']}

    def get_config(self):
        with self._lock:
            data = self._load()
            return self._config(data)

    def set_config(self, body):
        if not isinstance(body, dict) or set(body) - {'enabled', 'scopes', 'base_revision'}:
            raise ValueError('无效的同步配置')
        if 'enabled' in body and type(body['enabled']) is not bool:
            raise ValueError('同步开关必须为布尔值')
        scopes = body.get('scopes', {})
        if (not isinstance(scopes, dict) or set(scopes) - set(DEFAULT_SCOPES)
                or any(type(v) is not bool for v in scopes.values())):
            raise ValueError('无效的同步范围')
        with self._lock:
            data = self._load()
            if 'base_revision' in body:
                if type(body['base_revision']) is not int or body['base_revision'] < 0:
                    raise ValueError('无效的版本号')
                if body['base_revision'] != data['config_revision']:
                    raise SyncConflictError([{'key': 'config', 'revision': data['config_revision']}])
            enabled = body.get('enabled', data['enabled'])
            new_scopes = {**data['scopes'], **scopes}
            if enabled != data['enabled'] or new_scopes != data['scopes']:
                data.update(enabled=enabled, scopes=new_scopes, revision=data['revision'] + 1,
                            config_revision=data['config_revision'] + 1)
                self._save(data)
            return self._config(data)

    def get_state(self):
        with self._lock:
            return self._snapshot(self._load())

    def patch_state(self, changes):
        if not isinstance(changes, list) or not 1 <= len(changes) <= 100:
            raise ValueError('每次同步需要 1 至 100 项资料')
        prepared = []
        keys = set()
        for change in changes:
            if not isinstance(change, dict) or set(change) != {'key', 'value', 'base_revision'}:
                raise ValueError('无效的同步变更')
            base = change['base_revision']
            if type(base) is not int or base < 0:
                raise ValueError('无效的资料版本号')
            key, scope, value = validate_entry(change['key'], change['value'])
            if key in keys:
                raise ValueError('重复的同步资料键')
            keys.add(key)
            prepared.append((key, scope, value, base))
        with self._lock:
            data = self._load()
            if not data['enabled']:
                raise SyncDisabledError('服务器未开启跨设备同步')
            if any(not data['scopes'][scope] for _, scope, _, _ in prepared):
                raise SyncDisabledError('服务器未允许同步该范围')
            conflicts = []
            for key, _, _, base in prepared:
                revision = data['entries'].get(key, {}).get('revision', 0)
                if revision != base:
                    conflicts.append({'key': key, 'revision': revision})
            if conflicts:
                raise SyncConflictError(conflicts)
            data['revision'] += 1
            for key, _, value, _ in prepared:
                data['entries'][key] = {'value': value, 'revision': data['revision']}
            self._save(data)
            return self._snapshot(data)
