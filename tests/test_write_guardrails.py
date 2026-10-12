import json
from types import SimpleNamespace
import pytest
from garmin_connect_mcp.writes import WriteService,execute,invoke_write,validate
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.verification import calendar,devices,health
from test_writes import FakeClient,CASES


@pytest.mark.parametrize("operation,change",[
    ("schedule_workout", "duplicate"),("send_workout_to_device","missing_device"),
    ("set_activity_type","wrong_tuple"),("replace_strength_sets","foreign_set"),
])
def test_preflight_rejections_are_terminal_and_never_mutate(tmp_path,operation,change):
    class Client(FakeClient):
        def get_scheduled_workouts(self,*args):
            return {"calendarItems":[{"itemType":"workout","groupId":1,"date":"2026-10-12"}]}
        def get_devices(self): return [{"deviceId":999}]
        def get_activity_types(self): return [{"typeId":2,"typeKey":"cycling","parentTypeId":17}]
        def get_activity_exercise_sets(self,*args): return {"exerciseSets":[{"exerciseSetUUID":"owned"}]}
    service=WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    parameters=json.loads(json.dumps(CASES[operation]))
    if change=="foreign_set":parameters["payload"]["exerciseSets"][0]["exerciseSetUUID"]="foreign"
    draft=service.prepare(operation,parameters,"preflight-test")
    client=Client()
    result=execute(client,tmp_path,draft["draft_id"])
    assert result["status"]=="rejected"
    assert result["error"]["stage"]=="preflight"
    assert result["error"]["garmin_mutation_sent"] is False
    assert all(name.startswith("get_") for name,args,kwargs in client.calls)
    before=len(client.calls)
    assert execute(client,tmp_path,draft["draft_id"])==result
    assert len(client.calls)==before
    assert service.status(draft["draft_id"])["status"]=="rejected"


def test_sdk_401_mutation_replay_is_blocked():
    class Session:
        def __init__(self):self.calls=[]
        def request(self,method,*args,**kwargs):
            self.calls.append(method)
            return SimpleNamespace(status_code=401)
    session=Session()
    native=SimpleNamespace(_api_session=session)
    class Client:
        client=native
        def upload_workout(self,payload):
            self.client._api_session.request("GET","read")
            self.client._api_session.request("POST","write")
            self.client._api_session.request("POST","write")
    with pytest.raises(RequestError,match="WRITE_REPLAY_BLOCKED"):
        invoke_write(Client(),"upload_workout",{})
    assert session.calls==["GET","POST"]
    assert native._api_session is session


def test_old_prepared_invalid_draft_is_rejected_before_sdk_call(tmp_path):
    service=WriteService(tmp_path);service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare("schedule_workout",CASES["schedule_workout"],"old-draft-test")
    state=json.loads(service.store.load());next(iter(state.values()))["parameters"]={"workout_id":1,"date":"2026-10-12"}
    service.store.save(json.dumps(state));client=FakeClient()
    result=execute(client,tmp_path,draft["draft_id"])
    assert result["status"]=="rejected" and result["error"]["garmin_mutation_sent"] is False
    assert not client.calls


def test_verification_reads_filter_unrelated_private_fields():
    result=calendar({"calendarItems":[{"itemType":"activity","title":"private activity"},
        {"itemType":"workout","id":123,"groupId":456,"title":"Test","date":"2026-10-12","url":"private"}]})
    assert len(result["scheduled_workouts"])==1
    assert "private" not in json.dumps(result)
    assert "email" not in json.dumps(devices([{"deviceId":1,"displayName":"Test","email":"private"}]))
    assert "private" not in json.dumps(health({"userId":"private","notes":"private","measurementSummaries":[]}))


@pytest.mark.parametrize("operation,field,value",[
    ("add_body_composition","physique_rating",2.0),
    ("create_manual_activity","duration_min",1.0),
    ("replace_strength_sets","payload",{"activityId":999,"exerciseSets":[]}),
    ("update_workout","workout_json",{**CASES["create_workout"]["workout_json"],"workoutId":999}),
])
def test_strict_types_and_target_binding(operation,field,value):
    with pytest.raises(ValueError): validate(operation,{**CASES[operation],field:value})


@pytest.mark.parametrize("operation",[
    "create_gear","set_gear_default","add_gear_to_activity","remove_gear_from_activity",
    "delete_activity","delete_workout","delete_weigh_in","delete_weigh_ins","delete_blood_pressure",
    "create_manual_activity_from_json","import_activity","add_weigh_in_with_timestamps","request_reload",
    "update_menstrual_daily_log","update_menstrual_calendar","init_menstrual_cycle_setup",
    "confirm_menstrual_period_start","update_menstrual_settings","query_garmin_graphql","connectwebproxy",
])
def test_sdk_only_mutations_cannot_bypass_mcp_allowlist(operation):
    from garmin_connect_mcp.server import safe_call
    result=safe_call(validate,operation,{})
    assert result["error"]["code"]=="INVALID_WRITE_INPUT"
    assert result["error"]["garmin_request_sent"] is False
