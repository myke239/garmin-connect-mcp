import asyncio
import copy
import json
import pytest
from garmin_connect_mcp import writes
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.service import GarminService
from test_writes import CASES as ORIGINAL_CASES, FakeClient as OriginalClient
from garmin_connect_mcp.lifecycle import fingerprint
TARGET_TEMPLATE={"workoutId":123,"workoutName":"Synthetic","workoutSegments":[]}
TARGET={"workout_id":"123","expected_name":"Synthetic","expected_content_sha256":fingerprint(TARGET_TEMPLATE)}
CASES={**ORIGINAL_CASES,"rename_workout":{**TARGET,"workout_name":"Renamed"},
    "delete_workout":{**TARGET,"confirm_calendar_removal":True},
    "schedule_existing_workouts":{"workouts":[{"workout_id":"123","date_str":"2026-10-12"}]}}
class FakeClient(OriginalClient):
    def get_workout_by_id(self,workout_id): return copy.deepcopy(TARGET_TEMPLATE)



@pytest.mark.parametrize("operation",list(writes.COMMIT_TOOLS))
def test_reviewed_commit_matches_intent_and_uses_existing_journal(tmp_path,operation):
    client=FakeClient()
    service=writes.WriteService(tmp_path,runner=lambda directory,method,args,kwargs:writes.execute(client,directory,*args,**kwargs))
    service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare(operation,CASES[operation],"reviewed-test")
    args=draft["commit_arguments"];context={k:v for k,v in args.items() if k!="draft_id"}
    assert draft["commit_tool"]==writes.COMMIT_TOOLS[operation]
    for key in context:
        changed=copy.deepcopy(context);changed[key]=[] if key=="workouts" else "incorrect"
        with pytest.raises(writes.WriteInputError):service.commit_reviewed(args["draft_id"],operation,changed)
        assert not client.calls and service.status(args["draft_id"])["status"]=="prepared"
    with pytest.raises(writes.WriteInputError):service.commit_reviewed(args["draft_id"],"add_weight",context)
    assert not client.calls
    result=service.commit_reviewed(args["draft_id"],operation,context)
    assert result["status"]=="completed"
    count=len(client.calls)
    assert service.commit(args["draft_id"])==result
    assert service.commit_reviewed(args["draft_id"],operation,context)==result
    assert len(client.calls)==count


def test_reviewed_commit_preserves_expiry_disabled_and_old_drafts(tmp_path):
    client=FakeClient();service=writes.WriteService(tmp_path,runner=lambda directory,method,args,kwargs:writes.execute(client,directory,*args,**kwargs))
    service.settings.save(json.dumps({"enabled":True}))
    p=service.prepare("create_workout",CASES["create_workout"],"old-draft-test")
    context={k:v for k,v in p["commit_arguments"].items() if k!="draft_id"}
    state=json.loads(service.store.load());draft=next(iter(state.values()))
    assert "commit_arguments" not in draft # pre-existing journal format remains unchanged
    draft["expires_at"]=0;service.store.save(json.dumps(state))
    with pytest.raises(RequestError,match="DRAFT_EXPIRED"):service.commit_reviewed(p["draft_id"],"create_workout",context)
    assert not client.calls
    service.settings.save(json.dumps({"enabled":False}))
    with pytest.raises(RequestError,match="WRITES_DISABLED"):service.commit_reviewed(p["draft_id"],"create_workout",context)


@pytest.mark.parametrize("operation",list(writes.COMMIT_TOOLS))
def test_specialized_mcp_tools_keep_scope_annotations_and_workflow(tmp_path,monkeypatch,operation):
    original=writes.WriteService;client=FakeClient()
    monkeypatch.setattr(writes,"WriteService",lambda directory=None:original(directory,runner=lambda directory,method,args,kwargs:writes.execute(client,directory,*args,**kwargs)))
    service=original(tmp_path);service.settings.save(json.dumps({"enabled":True}))
    server=create_server(GarminService(TokenStore(tmp_path),runner=lambda *args:{}))
    async def call(name,args):
        result=await server.call_tool(name,args)
        return json.loads(result[0].text)
    async def run():
        tool=next(t for t in await server.list_tools() if t.name==writes.COMMIT_TOOLS[operation])
        assert not tool.annotations.readOnlyHint
        assert tool.annotations.destructiveHint==(operation in {"update_workout","rename_workout","delete_workout"})
        assert "garmin:write" in tool.meta["securitySchemes"][0]["scopes"]
        prepared=await call("prepare_garmin_write",{"operation":operation,"parameters":CASES[operation],"idempotency_key":"reviewed-mcp-test"})
        result=await call(prepared["commit_tool"],prepared["commit_arguments"])
        assert result["status"]=="completed"
    asyncio.run(run())


@pytest.mark.parametrize("operation",list(writes.COMMIT_TOOLS))
def test_specialized_remote_commit_requires_write_scope(tmp_path,operation):
    server=create_server(GarminService(TokenStore(tmp_path)),remote_access=True)
    context=writes.review_context(operation,CASES[operation],"0"*64)
    async def run():
        result=await server.call_tool(writes.COMMIT_TOOLS[operation],{"draft_id":"nonexistent-draft-id-000000",**context})
        assert "WRITE_SCOPE_REQUIRED" in str(result)
    asyncio.run(run())


def test_calendar_context_checks_nested_order_and_content(tmp_path):
    service=writes.WriteService(tmp_path,runner=lambda *args:pytest.fail("No runner for invalid context"))
    service.settings.save(json.dumps({"enabled":True}))
    parameters=copy.deepcopy(CASES["create_training_calendar"])
    parameters["workouts"].append({"date":"2026-10-13","workout":copy.deepcopy(parameters["workouts"][0]["workout"])})
    p=service.prepare("create_training_calendar",parameters,"calendar-context-test")
    context={k:v for k,v in p["commit_arguments"].items() if k!="draft_id"}
    bad=copy.deepcopy(context);bad["workouts"].reverse()
    with pytest.raises(writes.WriteInputError):service.commit_reviewed(p["draft_id"],"create_training_calendar",bad)
    bad=copy.deepcopy(context);bad["workouts"][0]["date"]="2026-10-14"
    with pytest.raises(writes.WriteInputError):service.commit_reviewed(p["draft_id"],"create_training_calendar",bad)


def test_unknown_reviewed_commit_never_replays(tmp_path):
    client=FakeClient(fail="upload_workout")
    service=writes.WriteService(tmp_path,runner=lambda directory,method,args,kwargs:writes.execute(client,directory,*args,**kwargs))
    service.settings.save(json.dumps({"enabled":True}))
    p=service.prepare("create_workout",CASES["create_workout"],"unknown-review-test")
    context={k:v for k,v in p["commit_arguments"].items() if k!="draft_id"}
    first=service.commit_reviewed(p["draft_id"],"create_workout",context)
    assert first["status"]=="unknown"
    count=len(client.calls)
    assert service.commit_reviewed(p["draft_id"],"create_workout",context)==first
    assert len(client.calls)==count
