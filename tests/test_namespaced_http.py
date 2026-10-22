"""Public path migration without account access or production token changes."""
from urllib.parse import parse_qs, urlsplit
from starlette.testclient import TestClient
from garmin_connect_mcp.endpoints import CANONICAL, connection_info
from garmin_connect_mcp.remote import create_deployment_app, OwnerProvider
from test_remote import ORIGIN, CALLBACK, CHALLENGE, VERIFIER


def test_namespace_full_oauth_and_resource_isolation(tmp_path):
    root = tmp_path / "oauth"
    old = OwnerProvider(ORIGIN, root)
    with old.state():
        pass
    app, provider = create_deployment_app(ORIGIN, directory=root)
    prefix = CANONICAL.prefix
    resource = ORIGIN + CANONICAL.mcp_path
    with TestClient(app, base_url=ORIGIN, follow_redirects=False) as client:
        metadata = client.get(CANONICAL.authorization_metadata).json()
        assert metadata["issuer"] == ORIGIN + prefix
        for name, route in [("authorization_endpoint", "/authorize"), ("token_endpoint", "/token"),
                            ("registration_endpoint", "/register"), ("revocation_endpoint", "/revoke")]:
            assert metadata[name] == ORIGIN + prefix + route
        protected = client.get(CANONICAL.resource_metadata).json()
        assert protected["resource"] == resource
        assert protected["authorization_servers"] == [ORIGIN + prefix]
        guard = client.post(CANONICAL.mcp_path, json={})
        assert guard.status_code == 401
        assert ORIGIN + CANONICAL.resource_metadata in guard.headers["www-authenticate"]
        assert client.post(prefix, json={}).headers["location"] == resource
        registered = client.post(prefix + "/register", json={"redirect_uris": [CALLBACK],
            "token_endpoint_auth_method": "none", "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"], "scope": "garmin:read"})
        assert registered.status_code == 201, registered.text
        identity = registered.json()["client_id"]
        params = {"client_id": identity, "response_type": "code", "redirect_uri": CALLBACK,
            "scope": "garmin:read", "state": "state", "code_challenge": CHALLENGE,
            "code_challenge_method": "S256", "resource": resource}
        redirect = client.get(prefix + "/authorize", params=params)
        assert redirect.status_code == 302, redirect.text
        assert redirect.headers["location"].startswith(ORIGIN + prefix + "/consent?")
        ticket = parse_qs(urlsplit(redirect.headers["location"]).query)["ticket"][0]
        page = client.get(prefix + "/consent", params={"ticket": ticket})
        assert f'action="{prefix}/consent"' in page.text
        with provider.state() as state:
            state["pending"][ticket]["approved"] = True
        redirect = client.get(prefix + "/consent", params={"ticket": ticket})
        code = parse_qs(urlsplit(redirect.headers["location"]).query)["code"][0]
        data = {"grant_type": "authorization_code", "client_id": identity, "code": code,
            "redirect_uri": CALLBACK, "code_verifier": VERIFIER, "resource": ORIGIN + "/mcp"}
        assert client.post(prefix + "/token", data=data).status_code == 400
        data["resource"] = resource
        tokens = client.post(prefix + "/token", data=data)
        assert tokens.status_code == 200, tokens.text
        headers = {"Authorization": "Bearer " + tokens.json()["access_token"]}
        assert client.get("/mcp", headers=headers).status_code == 401
        # Canonical token gets past OAuth; request itself lacks MCP protocol headers.
        assert client.get(CANONICAL.mcp_path, headers=headers).status_code != 401
        with old.state() as state:
            legacy_token = old.issue(state, "legacy-client", "legacy-family", ["garmin:read"]).access_token
        legacy_headers = {"Authorization": "Bearer " + legacy_token}
        assert client.get(CANONICAL.mcp_path, headers=legacy_headers).status_code == 401
        assert client.get("/mcp", headers=legacy_headers).status_code != 401
        discovery = client.post(CANONICAL.mcp_path, headers={**headers,
            "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
        assert discovery.status_code == 200, discovery.text
        assert len(discovery.json()["result"]["tools"]) == 58
        refresh = client.post(prefix + "/token", data={"grant_type": "refresh_token",
            "client_id": identity, "refresh_token": tokens.json()["refresh_token"], "resource": resource})
        assert refresh.status_code == 200, refresh.text
        revoked = client.post(prefix + "/revoke", data={"client_id": identity,
            "token": refresh.json()["access_token"]})
        assert revoked.status_code == 200
        assert client.get(CANONICAL.mcp_path, headers={"Authorization": "Bearer " + refresh.json()["access_token"]}).status_code == 401
        assert client.get("/.well-known/oauth-authorization-server").json()["issuer"].rstrip("/") == ORIGIN
        assert client.post(CANONICAL.mcp_path, content=b"x" * 20000).status_code == 401
        assert client.post(prefix + "/token", content=b"x" * 20000).status_code == 413
        with old.state() as state:
            assert identity not in state["clients"]


def test_fresh_install_leaves_root_free_and_legacy_can_be_disabled(tmp_path):
    for legacy in (None, False):
        app, _ = create_deployment_app(ORIGIN, directory=tmp_path / str(legacy), legacy=legacy)
        with TestClient(app, base_url=ORIGIN) as client:
            assert client.get("/register").status_code == 404
            assert client.get("/.well-known/oauth-authorization-server").status_code == 404
            assert client.post(CANONICAL.mcp_path, json={}).status_code == 401
    assert connection_info(ORIGIN)["server_url"] == ORIGIN + CANONICAL.mcp_path
