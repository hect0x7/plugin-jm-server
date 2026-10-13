"""Authenticated sync APIs; only a loopback client may change server policy."""
from flask import jsonify, request
from ..sync import MAX_BODY_BYTES, SyncConflictError, SyncDisabledError, SyncDataError


class SyncRoutesMixin:
    @staticmethod
    def _sync_editable():
        return request.remote_addr in ('127.0.0.1', '::1')

    def _sync_body(self):
        # A bound read also limits chunked requests lacking Content-Length.
        if request.content_length is not None and request.content_length > MAX_BODY_BYTES:
            raise ValueError('同步请求过大')
        raw = request.stream.read(MAX_BODY_BYTES + 1)
        if len(raw) > MAX_BODY_BYTES:
            raise ValueError('同步请求过大')
        import json
        try:
            body = json.loads(raw)
        except (ValueError, UnicodeError):
            raise ValueError('需要有效的 JSON 请求') from None
        if not isinstance(body, dict):
            raise ValueError('需要有效的 JSON 对象')
        return body

    def _sync_response(self, operation):
        if not self.verify():
            return jsonify({'error': 'Unauthorized'}), 401
        try:
            response = jsonify(operation())
            response.headers['Cache-Control'] = 'no-store'
            return response
        except SyncDisabledError as error:
            return jsonify({'error': str(error)}), 403
        except SyncConflictError as error:
            return jsonify({'error': str(error), 'conflicts': error.conflicts}), 409
        except SyncDataError as error:
            return jsonify({'error': str(error)}), 500
        except ValueError as error:
            # Request validation errors are raised before touching persistence.
            return jsonify({'error': str(error)}), 400
        except OSError:
            return jsonify({'error': '无法读写同步资料，请检查资料文件与访问权限'}), 500

    def api_sync_config(self):
        def operation():
            editable = self._sync_editable()
            if request.method == 'PUT':
                if not editable:
                    raise SyncDisabledError('只能在服务器电脑上修改同步范围')
                config = self.sync_manager.set_config(self._sync_body())
            else:
                config = self.sync_manager.get_config()
            return {**config, 'editable': editable}
        return self._sync_response(operation)

    def api_sync_state(self):
        def operation():
            if request.method == 'POST':
                body = self._sync_body()
                if set(body) != {'changes'}:
                    raise ValueError('需要 changes 同步变更列表')
                return self.sync_manager.patch_state(body['changes'])
            return self.sync_manager.get_state()
        return self._sync_response(operation)
