"""No real helper downloads or Codex configuration changes in default tests."""
import hashlib

import httpx
import pytest

from garmin_connect_mcp import setup_codex as setup
from garmin_connect_mcp import frozen_install


def test_existing_codex_is_reused_without_network(monkeypatch):
    monkeypatch.setattr(setup.shutil, 'which', lambda name: '/existing/codex')
    monkeypatch.setattr(setup, '_download', lambda: pytest.fail('Unexpected download'))
    assert setup.executable() == '/existing/codex'


@pytest.mark.parametrize('problem', [None, 'checksum', 'host', 'oversized'])
def test_download_is_bounded_verified_and_stays_in_application(tmp_path, monkeypatch, problem):
    root = tmp_path / 'application'
    payload = b'synthetic-codex-binary'
    expected = hashlib.sha256(payload).hexdigest()
    url = 'https://github.com/openai/codex/releases/download/test/codex-x86_64-pc-windows-msvc.exe'
    if problem == 'host':
        url = 'https://untrusted.example/codex.exe'
    metadata = {'assets': [{'name': 'codex-x86_64-pc-windows-msvc.exe', 'size': len(payload),
        'digest': 'sha256:' + expected, 'browser_download_url': url}]}
    calls = []
    def transport(request):
        calls.append(str(request.url))
        if request.url.host == 'api.github.com':
            return httpx.Response(200, json=metadata)
        body = b'changed' if problem == 'checksum' else payload
        if problem == 'oversized':
            body += b'extra'
        return httpx.Response(200, content=body)
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: original(transport=httpx.MockTransport(transport)))
    monkeypatch.setattr(frozen_install, 'default_root', lambda: root)
    if problem:
        with pytest.raises(setup.SetupError):
            setup._download()
        assert not list(root.rglob('codex.exe'))
        assert not list(root.rglob('*.download'))
    else:
        target = setup._download()
        assert target.startswith(str(root)) and (root / 'tools/codex' / expected / 'codex.exe').read_bytes() == payload
        assert setup._download() == target
        assert calls.count(url) == 1
