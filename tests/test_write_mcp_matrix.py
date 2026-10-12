"""Every operation through FastMCP discovery, preparation, commit and status."""
import asyncio
import json
import pytest
from garminconnect import Garmin
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp import writes
from test_writes import CASES
from test_sdk_write_contracts import Transport


@pytest.mark.parametrize("operation",list(CASES))
def test_mcp_write_workflow_and_durable_status(tmp_path,monkeypatch,operation):
    original=writes.WriteService
    client=Garmin();client.client=Transport()
    def runner(directory,method,args,kwargs):
        assert method=="mcp_commit_write"
        return writes.execute(client,directory,*args,**kwargs)
    monkeypatch.setattr(writes,"WriteService",lambda directory=None:original(directory,runner=runner))
    store=TokenStore(tmp_path);service=original(tmp_path);service.settings.save(json.dumps({"enabled":True}))
    server=create_server(GarminService(store,runner=lambda *args: {}))
    async def call(name,arguments):
        result=await server.call_tool(name,arguments)
        if isinstance(result,dict): return result
        return json.loads(result[0].text)
    async def exercise():
        contract=await call("get_garmin_write_schema",{"operation":operation})
        assert contract["operation"]==operation
        prepared=await call("prepare_garmin_write",{"operation":operation,"parameters":CASES[operation],
            "idempotency_key":"mcp-matrix-test"})
        assert prepared["status"]=="prepared"
        assert not client.client.calls
        committed=await call("commit_garmin_write",{"draft_id":prepared["draft_id"]})
        assert committed["status"]=="completed",committed
        calls=len(client.client.calls)
        status=await call("get_garmin_write_status",{"draft_id":prepared["draft_id"]})
        assert status["status"]=="completed"
        assert "parameters" not in status
        assert len(client.client.calls)==calls
        repeated=await call("commit_garmin_write",{"draft_id":prepared["draft_id"]})
        assert repeated==committed
        assert len(client.client.calls)==calls
    asyncio.run(exercise())
