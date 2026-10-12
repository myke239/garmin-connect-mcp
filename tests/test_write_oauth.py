import asyncio
import json
import time
from mcp.server.auth.provider import TokenError
from garmin_connect_mcp.remote import OwnerProvider, READ_SCOPE, WRITE_SCOPE
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.writes import WriteService
from garmin_connect_mcp.server import create_server
from test_remote import remote, register, CALLBACK, CHALLENGE, approved_code, exchange, ORIGIN, RESOURCE


def test_explicit_write_consent_and_refresh_preserve_scope(remote):
    client,provider=remote
    registration=register(client,scope="garmin:read garmin:write")
    assert registration.status_code == 201
    identity=registration.json()["client_id"]
    response=client.get("/authorize",params={"client_id":identity,"response_type":"code",
        "redirect_uri":CALLBACK,"scope":"garmin:read garmin:write","state":"explicit-write",
        "code_challenge":CHALLENGE,"code_challenge_method":"S256","resource":RESOURCE})
    from urllib.parse import parse_qs,urlsplit
    ticket=parse_qs(urlsplit(response.headers["location"]).query)["ticket"][0]
    assert "garmin:write" in client.get("/consent",params={"ticket":ticket}).text
    with provider.state() as state: state["pending"][ticket]["approved"]=True
    response=client.get("/consent",params={"ticket":ticket})
    code=parse_qs(urlsplit(response.headers["location"]).query)["code"][0]
    tokens=exchange(client,identity,code).json()
    assert set(tokens["scope"].split()) == {READ_SCOPE,WRITE_SCOPE}
    refreshed=client.post("/token",data={"grant_type":"refresh_token","client_id":identity,
        "refresh_token":tokens["refresh_token"],"resource":RESOURCE})
    assert refreshed.status_code == 200
    assert WRITE_SCOPE in refreshed.json()["scope"]


def test_read_grant_cannot_escalate_on_refresh(remote):
    client,provider=remote
    identity,code=approved_code(client,provider)
    tokens=exchange(client,identity,code).json()
    response=client.post("/token",data={"grant_type":"refresh_token","client_id":identity,
        "refresh_token":tokens["refresh_token"],"scope":"garmin:read garmin:write"})
    assert response.status_code == 400
    from mcp.shared.auth import OAuthClientInformationFull
    registered=asyncio.run(provider.get_client(identity))
    refresh=asyncio.run(provider.load_refresh_token(registered,tokens["refresh_token"]))
    with __import__('pytest').raises(TokenError):
        asyncio.run(provider.exchange_refresh_token(registered,refresh,[READ_SCOPE,WRITE_SCOPE]))


def test_local_write_opt_in_and_tool_annotations(tmp_path):
    store=TokenStore(tmp_path)
    writes=WriteService(tmp_path)
    backend=GarminService(store,runner=lambda *args: {})
    server=create_server(backend)
    async def exercise():
        tools=await server.list_tools()
        write_tools=[tool for tool in tools if tool.name in {"prepare_garmin_write","commit_garmin_write"}]
        assert len(write_tools)==2
        assert all(not tool.annotations.readOnlyHint for tool in write_tools)
        assert all(WRITE_SCOPE in tool.meta["securitySchemes"][0]["scopes"] for tool in write_tools)
        result=await server.call_tool("prepare_garmin_write",{"operation":"add_weight",
            "parameters":{"weight":70,"timestamp":"2026-10-11T12:00:00+00:00"},"idempotency_key":"local-opt-in"})
        assert "WRITES_DISABLED" in str(result)
        writes.settings.save(json.dumps({"enabled":True}))
        result=await server.call_tool("prepare_garmin_write",{"operation":"add_weight",
            "parameters":{"weight":70,"timestamp":"2026-10-11T12:00:00+00:00"},"idempotency_key":"local-opt-in"})
        assert "draft_id" in str(result)
    asyncio.run(exercise())


def test_schedule_preparation_through_mcp(tmp_path):
    writes=WriteService(tmp_path)
    writes.settings.save(json.dumps({"enabled":True}))
    def no_network(*args):
        raise AssertionError("Preparation must not call Garmin")
    server=create_server(GarminService(TokenStore(tmp_path),runner=no_network))
    async def exercise():
        invalid=await server.call_tool("prepare_garmin_write",{"operation":"schedule_workout",
            "parameters":{"workout_id":"123","date":"2026-10-12"},"idempotency_key":"mcp-invalid"})
        assert "INVALID_WRITE_INPUT" in str(invalid)
        assert "date_str" in str(invalid)
        valid=await server.call_tool("prepare_garmin_write",{"operation":"schedule_workout",
            "parameters":{"workout_id":"123","date_str":"2026-10-12"},"idempotency_key":"mcp-valid"})
        assert "draft_id" in str(valid)
        assert "prepared" in str(valid)
    asyncio.run(exercise())
