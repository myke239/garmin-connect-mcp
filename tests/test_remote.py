"""Exercise the full HTTP OAuth gate without Garmin credentials or a public tunnel."""
import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

import pytest
from starlette.testclient import TestClient

from garmin_connect_mcp.remote import create_http_app, key, public_origin

ORIGIN = "https://garmin.example.com"
RESOURCE = ORIGIN + "/mcp"
CALLBACK = "https://chatgpt.com/connector/oauth/test-callback-id"
VERIFIER = "a" * 64
CHALLENGE = base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip("=")


@pytest.fixture
def remote(tmp_path):
    app, provider = create_http_app(ORIGIN, directory=tmp_path / "oauth")
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        yield client, provider


def register(client, callback=CALLBACK):
    return client.post("/register", json={"redirect_uris": [callback],
        "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"], "scope": "garmin:read"})


def pending(client):
    registered = register(client)
    assert registered.status_code == 201, registered.text
    identity = registered.json()["client_id"]
    response = client.get("/authorize", params={"client_id": identity, "response_type": "code",
        "redirect_uri": CALLBACK, "scope": "garmin:read", "state": "browser-state",
        "code_challenge": CHALLENGE, "code_challenge_method": "S256", "resource": RESOURCE})
    assert response.status_code == 302, response.text
    ticket = parse_qs(urlsplit(response.headers["location"]).query)["ticket"][0]
    return identity, ticket


def approved_code(client, provider):
    identity, ticket = pending(client)
    page = client.get("/consent", params={"ticket": ticket})
    assert page.status_code == 200 and "on your PC" in page.text
    assert "code=" not in page.text
    # Simulate only the owner-local approval; no HTTP endpoint can perform it.
    with provider.state() as state:
        state["pending"][ticket]["approved"] = True
    redirect = client.get("/consent", params={"ticket": ticket})
    assert redirect.status_code == 302
    query = parse_qs(urlsplit(redirect.headers["location"]).query)
    assert query["state"] == ["browser-state"]
    assert client.get("/consent", params={"ticket": ticket}).status_code == 400
    return identity, query["code"][0]


def exchange(client, identity, code, verifier=VERIFIER, resource=RESOURCE):
    return client.post("/token", data={"grant_type": "authorization_code", "client_id": identity,
        "code": code, "redirect_uri": CALLBACK, "code_verifier": verifier, "resource": resource})


def test_unauthorized_discovery_and_no_browser_approval(remote):
    client, _ = remote
    for method in ("GET", "POST", "DELETE"):
        response = client.request(method, "/mcp", json={})
        assert response.status_code == 401
        assert "resource_metadata" in response.headers["www-authenticate"]
    assert client.get("/.well-known/oauth-authorization-server").json()["code_challenge_methods_supported"] == ["S256"]
    metadata = client.get("/.well-known/oauth-protected-resource/mcp").json()
    assert metadata["resource"] == RESOURCE
    assert client.get("/mcp", headers={"Authorization": "Bearer invented"}).status_code == 401
    assert client.post("/consent", data={"approved": "true"}).status_code == 405
    identity, ticket = pending(client)
    assert client.get("/consent", params={"ticket": ticket, "approved": "true"}).status_code == 200
    assert exchange(client, identity, ticket).status_code == 400


def test_pkce_replay_refresh_revocation_and_restart(remote):
    client, provider = remote
    identity, code = approved_code(client, provider)
    assert exchange(client, identity, code, verifier="wrong").status_code == 400
    token_response = exchange(client, identity, code)
    assert token_response.status_code == 200, token_response.text
    tokens = token_response.json()
    assert exchange(client, identity, code).status_code == 400
    headers = {"Authorization": "Bearer " + tokens["access_token"],
               "Accept": "application/json, text/event-stream"}
    initialized = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 1,
        "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"}}})
    assert initialized.status_code == 200, initialized.text
    listing = client.post("/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 2,
        "method": "tools/list", "params": {}}).json()
    assert len(listing["result"]["tools"]) == 7
    assert all(tool["annotations"]["readOnlyHint"] for tool in listing["result"]["tools"])
    # Encrypted state survives a new provider process/object.
    from garmin_connect_mcp.remote import OwnerProvider
    reloaded = OwnerProvider(ORIGIN, provider.store.directory)
    import asyncio
    assert asyncio.run(reloaded.load_access_token(tokens["access_token"])) is not None
    refreshed = client.post("/token", data={"grant_type": "refresh_token", "client_id": identity,
        "refresh_token": tokens["refresh_token"], "resource": RESOURCE})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["refresh_token"] != tokens["refresh_token"]
    assert client.post("/token", data={"grant_type": "refresh_token", "client_id": identity,
        "refresh_token": tokens["refresh_token"], "resource": RESOURCE}).status_code == 400
    assert client.get("/mcp", headers=headers).status_code == 401
    latest = refreshed.json()
    revoked = client.post("/revoke", data={"client_id": identity, "token": latest["refresh_token"],
                                            "token_type_hint": "refresh_token"})
    assert revoked.status_code == 200
    assert client.get("/mcp", headers={"Authorization": "Bearer " + latest["access_token"]}).status_code == 401


def test_callback_origin_size_and_resource_rejection(remote):
    client, provider = remote
    assert register(client, "https://attacker.example/callback").status_code == 400
    assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 403
    assert client.get("/health", headers={"Origin": "https://attacker.example"}).status_code == 403
    assert client.post("/register", content="x" * 16385).status_code == 413
    identity, code = approved_code(client, provider)
    assert exchange(client, identity, code, resource="https://attacker.example/mcp").status_code == 400
    assert exchange(client, identity, code).status_code == 200
    with pytest.raises(ValueError):
        public_origin("http://garmin.example.com")


def test_expiration_and_terminal_approval(remote, monkeypatch):
    client, provider = remote
    _, ticket = pending(client)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    with pytest.raises(ValueError):
        provider.approve(ticket)
    assert client.get("/consent", params={"ticket": ticket}).status_code == 200
    with provider.state() as state:
        state["pending"][ticket]["expires_at"] = time.time() - 1
    assert client.get("/consent", params={"ticket": ticket}).status_code == 400
