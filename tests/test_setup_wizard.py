"""Exercise page transitions with fake services; never signs in or starts tunnels."""
import time
import os
from types import SimpleNamespace

import pytest

tk = pytest.importorskip('tkinter')

from garmin_connect_mcp import setup_wizard as wizard


@pytest.fixture
def app():
    try:
        root = tk.Tk()
    except tk.TclError:
        if os.name != 'nt' and not os.environ.get('DISPLAY'):
            pytest.skip('No graphical display; frozen CI constructs the wizard under Xvfb')
        raise
    root.withdraw()
    backend = SimpleNamespace(existing_origin=lambda: '', session_saved=lambda: False,
        install=lambda: None, connect_codex=lambda: None)
    result = wizard.Application(root, backend=backend)
    yield result
    if not result.cancelled.is_set():
        result.close()


def pump(app, page):
    end = time.monotonic() + 3
    while app.page != page and time.monotonic() < end:
        app.root.update()
        time.sleep(.005)
    assert app.page == page


def test_begin_install_is_the_only_primary_action(app):
    assert app.primary['text'] == 'Begin Install'
    assert str(app.back['state']) == 'disabled'
    assert not app.content.winfo_children()
    app.primary.invoke()
    pump(app, 'signin')
    assert app.primary['text'] == 'Sign in'
    assert app.password['show']


def test_failed_login_never_advances_or_displays_secrets(app, monkeypatch):
    app.show_page('signin')
    app.email.insert(0, 'synthetic@example.com')
    app.password.insert(0, 'synthetic-password')
    def fail(*args):
        raise RuntimeError('synthetic-password')
    monkeypatch.setattr(wizard, 'login', fail)
    app.primary.invoke()
    assert app.email.get() == '' and app.password.get() == ''
    deadline = time.monotonic() + 3
    while app.busy and time.monotonic() < deadline:
        app.root.update()
        time.sleep(.005)
    assert app.page == 'signin' and not app.busy
    assert 'synthetic-password' not in app.message['text']


def test_mfa_then_codex_has_one_action_per_page(app, monkeypatch):
    def fake_login(email, password, prompt, cancelled):
        assert prompt() == '123456'
    monkeypatch.setattr(wizard, 'login', fake_login)
    app.show_page('signin')
    app.email.insert(0, 'synthetic@example.com')
    app.password.insert(0, 'synthetic-password')
    app.primary.invoke()
    pump(app, 'mfa')
    assert app.primary['text'] == 'Next' and str(app.back['state']) == 'disabled'
    app.code.insert(0, '123456')
    app.primary.invoke()
    pump(app, 'client')
    app.client.set('codex')
    app.primary.invoke()
    assert app.page == 'codex'
    app.primary.invoke()
    pump(app, 'finish')
    assert app.primary['text'] == 'Close'


def test_shared_connection_keeps_choice_and_never_runs_new_tunnel(app, monkeypatch):
    calls = []
    app.backend.check_server = lambda origin: calls.append(origin) or origin + '/mcp/garmin-connect/'
    app.backend.find_request = lambda ticket: setattr(app.backend, 'review', {'resource': 'https://shared.example/mcp/garmin-connect/',
        'client_id': 'synthetic-client', 'callback': 'https://chatgpt.com/oauth/callback', 'scopes': ['garmin:read']})
    app.backend.approve = lambda: calls.append('approve')
    app.backend.verify_chatgpt = lambda: calls.append('verify')
    monkeypatch.setattr(wizard.webbrowser, 'open', lambda url: calls.append(url))
    app.show_page('hosting')
    app.hosting.set('existing')
    app.primary.invoke()
    app.origin.set('https://shared.example')
    app.go_back()
    assert app.hosting.get() == 'existing'
    app.primary.invoke()
    assert app.origin.get() == 'https://shared.example'
    app.primary.invoke()
    pump(app, 'chatgpt')
    app.primary.invoke()
    assert app.page == 'request'
    app.ticket.insert(0, 'synthetic-ticket')
    app.primary.invoke()
    pump(app, 'review')
    assert app.primary['text'] == 'Approve connection'
    app.primary.invoke()
    pump(app, 'confirm')
    app.primary.invoke()
    pump(app, 'finish')
    assert calls == ['https://shared.example', 'https://chatgpt.com/plugins', 'approve', 'verify']
