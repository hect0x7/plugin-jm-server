"""
CLI 单元测试。

只测试参数解析与到 JmServer 的映射, 不真正启动服务器(不绑定端口)。
运行: python -m pytest tests/ -q   或   python tests/test_cli.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from jm_view_server import cli  # noqa: E402
from jm_view_server.app import JmServer  # noqa: E402


def parse(argv):
    return cli.build_parser().parse_args(argv)


@pytest.fixture(autouse=True)
def isolated_user_data(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path))
    monkeypatch.setenv('USERPROFILE', str(tmp_path))


# ---------- 默认值 ----------

def test_defaults():
    args = parse([])
    assert args.path == '.'
    assert args.password == ''
    assert args.host == '0.0.0.0'
    assert args.port == JmServer.DEFAULT_PORT
    assert args.ssl is False
    assert args.option is None
    assert args.ip_whitelist is None
    assert args.current_path is None
    assert args.env is None
    assert args.debug is False
    assert args.reload is True


def test_positional_path_and_short_flags():
    args = parse(['/data/comics', '-P', 'pw', '-p', '8080', '-H', '127.0.0.1', '-s'])
    assert args.path == '/data/comics'
    assert args.password == 'pw'
    assert args.port == 8080
    assert args.host == '127.0.0.1'
    assert args.ssl is True


# ---------- env 解析 ----------

def test_parse_env_ok():
    assert cli.parse_env(['A=1', 'B=x=y']) == {'A': '1', 'B': 'x=y'}


def test_parse_env_none():
    assert cli.parse_env(None) == {}


def test_parse_env_bad_raises():
    with pytest.raises(ValueError):
        cli.parse_env(['NOEQUALS'])


# ---------- ip 白名单解析 ----------

def test_parse_ip_whitelist():
    assert cli.parse_ip_whitelist('1.1.1.1, 2.2.2.2 ,') == ['1.1.1.1', '2.2.2.2']
    assert cli.parse_ip_whitelist('') is None
    assert cli.parse_ip_whitelist(None) is None


# ---------- run kwargs 映射 ----------

def test_run_kwargs_plain():
    args = parse(['x', '-p', '8080', '-H', '0.0.0.0'])
    assert cli.build_run_kwargs(args) == {
        'host': '0.0.0.0', 'port': 8080, 'debug': False,
        'use_reloader': True, 'reloader_type': 'stat',
    }


def test_debug_requires_explicit_opt_in():
    assert cli.build_run_kwargs(parse(['--debug']))['debug'] is True
    assert cli.build_run_kwargs(parse(['--no-debug']))['debug'] is False
    with pytest.raises(SystemExit):
        parse(['--debug', '--no-debug'])


@pytest.mark.parametrize('flags,debug,reload', [
    ([], False, True), (['--no-debug'], False, True),
    (['--no-reload'], False, False), (['--debug'], True, True),
    (['--debug', '--no-reload'], True, False), (['--reload'], False, True),
])
def test_reload_and_debug_are_independent(flags, debug, reload):
    kwargs = cli.build_run_kwargs(parse(flags))
    assert kwargs['debug'] is debug
    assert kwargs['use_reloader'] is reload


def test_conflicting_reload_flags_are_rejected():
    with pytest.raises(SystemExit):
        parse(['--reload', '--no-reload'])


@pytest.mark.parametrize('configured_key', [None, '', 'fixture-configured-key'])
def test_reloader_keeps_login_cookie_valid(tmp_path, monkeypatch, configured_key):
    monkeypatch.setenv('FLASK_SECRET_KEY', 'temporary-test-key')
    if configured_key is None:
        monkeypatch.delenv('FLASK_SECRET_KEY')
    else:
        monkeypatch.setenv('FLASK_SECRET_KEY', configured_key)
    args = parse([str(tmp_path), '-P', 'fixture-password'])
    parent = cli.build_server(args)
    monkeypatch.setattr(parent.app, 'run', lambda **kwargs: None)
    parent.run(**cli.build_run_kwargs(args))
    with parent.app.test_request_context():
        cookie = parent.app.session_interface.get_signing_serializer(parent.app).dumps({'password': args.password})
    child = cli.build_server(args)
    assert child.app.session_interface.get_signing_serializer(child.app).loads(cookie)['password'] == args.password
    assert child.app.debug is False


def test_explicit_env_secret_applies_to_parent_and_reloader_child(tmp_path, monkeypatch):
    monkeypatch.setenv('FLASK_SECRET_KEY', 'previous-fixture-key')
    args = parse([str(tmp_path), '-e', 'FLASK_SECRET_KEY=selected-fixture-key'])
    parent = cli.build_server(args)
    assert parent.app.secret_key == 'selected-fixture-key'
    monkeypatch.setattr(parent.app, 'run', lambda **kwargs: None)
    parent.run(**cli.build_run_kwargs(args))
    assert cli.build_server(args).app.secret_key == parent.app.secret_key


def test_templates_refresh_without_debug_or_process_restart(tmp_path):
    from jinja2 import FileSystemLoader
    template = tmp_path / 'live.html'
    template.write_text('Before', encoding='utf-8')
    server = cli.build_server(parse([str(tmp_path)]))
    server.app.jinja_loader = FileSystemLoader(str(tmp_path))
    assert server.app.jinja_env.get_template('live.html').render() == 'Before'
    before = template.stat().st_mtime
    template.write_text('After', encoding='utf-8')
    os.utime(template, (before + 2, before + 2))
    assert server.app.jinja_env.get_template('live.html').render() == 'After'
    assert server.app.debug is False


def test_run_kwargs_ssl_and_no_debug():
    args = parse(['x', '-s', '--no-debug'])
    kw = cli.build_run_kwargs(args)
    assert kw['ssl_context'] == 'adhoc'
    assert kw['debug'] is False


# ---------- 构造 JmServer(不启动) ----------

def test_build_server_basic():
    args = parse(['/tmp', '-P', 'secret', '-p', '8080'])
    server = cli.build_server(args)
    assert isinstance(server, JmServer)
    assert server.password == 'secret'
    assert server.file_manager.default_path == '/tmp'
    # port 进入 extra, 供首页拼接局域网地址
    assert server.extra.get('port') == 8080
    assert server.ip_whitelist is None


def test_build_server_with_whitelist():
    args = parse(['/tmp', '--ip-whitelist', '10.0.0.1,10.0.0.2'])
    server = cli.build_server(args)
    assert server.ip_whitelist == ['10.0.0.1', '10.0.0.2']


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-q']))
