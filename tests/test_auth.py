import json
import os

import pytest

from garmin_connect_mcp.auth import TokenStore, restore_session


def test_store_roundtrip_and_permissions(tmp_path):
    store = TokenStore(tmp_path / "private")
    tokens = json.dumps({"refresh_token": "synthetic-secret"})
    store.save(tokens)
    assert store.load() == tokens
    if os.name == "nt":
        assert b"synthetic-secret" not in store.path.read_bytes()
        import win32security
        descriptor = win32security.GetNamedSecurityInfo(str(store.path), win32security.SE_FILE_OBJECT,
                                                        win32security.DACL_SECURITY_INFORMATION)
        assert descriptor.GetSecurityDescriptorControl()[0] & win32security.SE_DACL_PROTECTED
        assert descriptor.GetSecurityDescriptorDacl().GetAceCount() == 2
    else:
        assert store.path.stat().st_mode & 0o777 == 0o600
    store.clear()
    assert not store.exists()


def test_resume_persists_refreshed_tokens(tmp_path):
    store = TokenStore(tmp_path / "private")
    store.save('{"token":"old"}')
    class FakeClient:
        client = None
        def __init__(self):
            self.client = self
        def login(self, tokens):
            assert json.loads(tokens)["token"] == "old"
        def dumps(self):
            return '{"token":"refreshed"}'
    restore_session(store, FakeClient)
    assert json.loads(store.load())["token"] == "refreshed"


def test_corrupted_store_fails_closed(tmp_path):
    store = TokenStore(tmp_path)
    store.path.write_bytes(b"corrupt")
    with pytest.raises(Exception):
        store.load()


def test_bad_json_does_not_replace_session(tmp_path):
    store = TokenStore(tmp_path)
    store.save('{"token":"good"}')
    with pytest.raises(ValueError):
        store.save("broken")
    assert json.loads(store.load())["token"] == "good"

