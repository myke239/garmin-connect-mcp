"""Local setup contracts: synthetic credentials, exact consent and hidden processes."""
import json
import subprocess
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from garmin_connect_mcp import setup_service as setup
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.endpoints import CANONICAL
from garmin_connect_mcp.remote import create_http_app
from test_remote import ORIGIN, CALLBACK, CHALLENGE, VERIFIER


@pytest.fixture
def private(tmp_path, monkeypatch):
    monkeypatch.setenv('GARMIN_MCP_DATA_DIR', str(tmp_path / 'private'))
    return tmp_path / 'private'


def test_login_mfa_verifies_before_protected_save(private, capsys):
    events = []
    class Client:
        password = 'synthetic-password'
        client = SimpleNamespace(dumps=lambda: '{"synthetic":"session"}')
        def login(self):
            events.append('login')
            assert self.prompt() == '123456'
        def get_activities(self, start, count):
            events.append('verify')
            assert (start, count) == (0, 1)
    client = Client()
    def factory(email, password, prompt_mfa):
        assert email == 'test@example.com' and password == 'synthetic-password'
        client.prompt = prompt_mfa
        return client
    setup.login(' test@example.com ', 'synthetic-password', lambda: '123456', factory=factory)
    assert events == ['login', 'verify']
    assert json.loads(TokenStore(private).load()) == {'synthetic': 'session'}
    assert client.password is None and capsys.readouterr().out == ''


@pytest.mark.parametrize('failure', ['credentials', 'read', 'cancel'])
def test_failed_or_cancelled_login_preserves_existing_session(private, failure):
    store = TokenStore(private)
    store.save('{"original":true}')
    client = SimpleNamespace(password='private-password', client=SimpleNamespace(dumps=lambda: '{"replacement":true}'))
    def fail():
        raise RuntimeError('private-password must not reach the UI')
    client.login = fail if failure == 'credentials' else lambda: None
    client.get_activities = (lambda *args: fail()) if failure == 'read' else lambda *args: None
    with pytest.raises(setup.SetupError) as error:
        setup.login('test@example.com', 'private-password', lambda: '', cancelled=lambda: failure == 'cancel', factory=lambda *a, **k: client)
    assert 'private-password' not in str(error.value)
    assert json.loads(store.load()) == {'original': True}
    assert client.password is None


def request(client):
    identity = client.post(CANONICAL.prefix + '/register', json={'redirect_uris': [CALLBACK],
        'token_endpoint_auth_method': 'none', 'grant_types': ['authorization_code', 'refresh_token'],
        'response_types': ['code'], 'scope': 'garmin:read garmin:write'}).json()['client_id']
    response = client.get(CANONICAL.prefix + '/authorize', params={'client_id': identity,
        'response_type': 'code', 'redirect_uri': CALLBACK, 'scope': 'garmin:read', 'state': 'state',
        'code_challenge': CHALLENGE, 'code_challenge_method': 'S256', 'resource': ORIGIN + CANONICAL.mcp_path})
    return identity, parse_qs(urlsplit(response.headers['location']).query)['ticket'][0]


def test_exact_local_gui_review_completes_oauth_without_scope_expansion(private):
    app, provider = create_http_app(ORIGIN, directory=private / 'remote-oauth', endpoint=CANONICAL)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        identity, ticket = request(client)
        _, other = request(client)
        with pytest.raises(setup.SetupError):
            setup.connection_request(ORIGIN, '')
        review = setup.connection_request(ORIGIN, ticket)
        assert review['client_id'] == identity and review['scopes'] == ['garmin:read']
        assert ticket in client.get(CANONICAL.prefix + '/consent', params={'ticket': ticket}).text
        setup.approve_connection(ORIGIN, review)
        with provider.state() as state:
            assert state['pending'][ticket]['approved'] and not state['pending'][other]['approved']
            assert not state['access']
        response = client.get(CANONICAL.prefix + '/consent', params={'ticket': ticket})
        code = parse_qs(urlsplit(response.headers['location']).query)['code'][0]
        token = client.post(CANONICAL.prefix + '/token', data={'grant_type': 'authorization_code',
            'client_id': identity, 'code': code, 'redirect_uri': CALLBACK,
            'code_verifier': VERIFIER, 'resource': ORIGIN + CANONICAL.mcp_path})
        assert token.status_code == 200 and token.json()['scope'] == 'garmin:read'


@pytest.mark.parametrize('change', ['scope', 'expire', 'old'])
def test_gui_rejects_changed_expired_or_preexisting_request(private, change):
    app, provider = create_http_app(ORIGIN, directory=private / 'remote-oauth', endpoint=CANONICAL)
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        _, ticket = request(client)
        if change == 'old':
            with pytest.raises(setup.SetupError):
                setup.connection_request(ORIGIN, ticket, since=10**12)
            return
        review = setup.connection_request(ORIGIN, ticket)
        with provider.state() as state:
            if change == 'scope':
                state['pending'][ticket]['params']['scopes'].append('garmin:write')
            else:
                state['pending'][ticket]['expires_at'] = 0
        with pytest.raises(setup.SetupError):
            setup.approve_connection(ORIGIN, review)
        with provider.state() as state:
            assert not state['access']
            assert not state['pending'].get(ticket, {}).get('approved', False)


def test_backend_uses_hidden_internal_commands_without_secrets(private, monkeypatch):
    backend = setup.Backend()
    backend.frozen = True
    backend.runtime = ['D:/isolated/garmin-connect.exe']
    calls = []
    def run(args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, b'', b'')
    monkeypatch.setattr(setup.subprocess, 'run', run)
    backend.verify()
    assert calls[0][0] == ['D:/isolated/garmin-connect.exe', '--internal-module', 'cli', 'verify']
    assert calls[0][1]['capture_output'] and calls[0][1]['timeout'] <= 90
    if setup.os.name == 'nt':
        assert calls[0][1]['creationflags'] == subprocess.CREATE_NO_WINDOW


def test_new_tunnel_refuses_occupied_shared_port_without_changing_token(private, monkeypatch):
    store = TokenStore(private / 'remote-tunnel')
    store.save('{"authtoken":"original-synthetic-token"}')
    class Occupied:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    monkeypatch.setattr(setup.socket, 'create_connection', lambda *a, **k: Occupied())
    with pytest.raises(setup.SetupError, match='already running'):
        setup.Backend().start_tunnel('replacement-synthetic-token')
    assert json.loads(store.load())['authtoken'] == 'original-synthetic-token'


def test_remote_checks_are_bounded_and_validate_garmin_namespace(private, monkeypatch):
    import httpx
    client_type = httpx.Client
    requested = []
    def transport(request):
        requested.append(request.url.path)
        if request.method == 'POST':
            return httpx.Response(401, json={'error': 'unauthorized'})
        return httpx.Response(200, json={'resource': ORIGIN + CANONICAL.mcp_path,
            'authorization_servers': [ORIGIN + CANONICAL.prefix]})
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: client_type(transport=httpx.MockTransport(transport)))
    backend = setup.Backend()
    assert backend.check_server(ORIGIN) == ORIGIN + CANONICAL.mcp_path
    assert requested == [CANONICAL.resource_metadata, CANONICAL.mcp_path]
    with client_type(transport=httpx.MockTransport(lambda request: httpx.Response(200, content=b'x' * 100))) as client:
        with pytest.raises(setup.SetupError, match='too large'):
            setup.bounded_request(client, 'GET', ORIGIN, 10)


def test_new_windows_tunnel_registers_startup_after_server_verification(private, monkeypatch):
    def unused_port(*args, **kwargs):
        raise ConnectionRefusedError()
    monkeypatch.setattr(setup.socket, 'create_connection', unused_port)
    backend = setup.Backend()
    calls = []
    monkeypatch.setattr(backend, 'run', lambda operation: calls.append(operation))
    monkeypatch.setattr(backend, 'existing_origin', lambda: ORIGIN)
    def check(origin):
        assert calls == ['background-start']
        return origin + CANONICAL.mcp_path
    monkeypatch.setattr(backend, 'check_server', check)
    assert backend.start_tunnel('synthetic-token') == ORIGIN + CANONICAL.mcp_path
    assert calls == (['background-start', 'background-install'] if setup.os.name == 'nt' else ['background-start'])
