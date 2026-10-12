import json
import base64
import pytest
from garmin_connect_mcp.writes import WriteService, validate, execute, METHODS
from garmin_connect_mcp.runtime import RequestError

STAMP = "2026-10-11T12:00:00+00:00"
WORKOUT = {"workoutName":"Synthetic easy run","sportType":{"sportTypeId":1,"sportTypeKey":"running"},
    "workoutSegments":[{"segmentOrder":1,"sportType":{"sportTypeId":1,"sportTypeKey":"running"},
    "workoutSteps":[{"type":"ExecutableStepDTO","stepOrder":1,"stepType":{"stepTypeId":3,"stepTypeKey":"interval"},
    "endCondition":{"conditionTypeId":2,"conditionTypeKey":"time"},"endConditionValue":600,
    "targetType":{"workoutTargetTypeId":1,"workoutTargetTypeKey":"no.target"}}]}]}
CASES = {
    "create_workout":{"workout_json":WORKOUT},
    "update_workout":{"workout_id":1,"workout_json":WORKOUT},
    "schedule_workout":{"workout_id":1,"date_str":"2026-10-12"},
    "unschedule_workout":{"scheduled_workout_id":2},
    "send_workout_to_device":{"workout_id":1,"device_id":3},
    "create_manual_activity":{"start_datetime":"2026-10-11T12:00:00","time_zone":"UTC","type_key":"running","distance_km":5,"duration_min":30,"activity_name":"Synthetic run"},
    "upload_activity_file":{"format":"gpx","content_base64":base64.b64encode(b'<gpx version="1.1"></gpx>').decode()},
    "set_activity_name":{"activity_id":"1","title":"Synthetic"},
    "set_activity_description":{"activity_id":"1","description":"Synthetic"},
    "set_activity_type":{"activity_id":"1","type_id":1,"type_key":"running","parent_type_id":17},
    "replace_strength_sets":{"activity_id":1,"payload":{"exerciseSets":[{"repetitionCount":10}]}},
    "add_weight":{"weight":70,"unitKey":"kg","timestamp":STAMP},
    "add_body_composition":{"weight":70,"percent_fat":20,"timestamp":STAMP},
    "add_hydration":{"value_in_ml":250,"timestamp":STAMP,"cdate":"2026-10-11"},
    "add_blood_pressure":{"systolic":120,"diastolic":80,"pulse":60,"timestamp":STAMP},
    "create_training_calendar":{"workouts":[{"date":"2026-10-12","workout":WORKOUT}]},
}


class FakeClient:
    def __init__(self, fail=None): self.calls=[]; self.fail=fail
    def __getattr__(self,name):
        def call(*args,**kwargs):
            self.calls.append((name,args,kwargs))
            if name == self.fail: raise TimeoutError("private upstream detail")
            return {"workoutId":123,"activityId":456,"privateField":"not returned"}
        return call


@pytest.mark.parametrize("operation", list(CASES))
def test_each_operation_is_previewed_and_committed_once(tmp_path,operation):
    service=WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare(operation,CASES[operation],"unique-intent")
    client=FakeClient()
    result=execute(client,tmp_path,draft["draft_id"])
    assert result["status"] == "completed"
    assert "privateField" not in json.dumps(result)
    count=len(client.calls)
    assert execute(client,tmp_path,draft["draft_id"]) == result
    assert len(client.calls) == count
    assert service.prepare(operation,CASES[operation],"unique-intent")["status"] == "completed"


def test_disabled_validation_replay_and_expiry(tmp_path):
    service=WriteService(tmp_path)
    with pytest.raises(RequestError,match="WRITES_DISABLED"):
        service.prepare("add_weight",CASES["add_weight"],"test-key")
    service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare("add_weight",CASES["add_weight"],"test-key")
    with pytest.raises(ValueError): service.prepare("add_hydration",CASES["add_hydration"],"test-key")
    state=json.loads(service.store.load())
    next(iter(state.values()))["expires_at"]=0
    service.store.save(json.dumps(state))
    client=FakeClient()
    with pytest.raises(RequestError,match="DRAFT_EXPIRED"): execute(client,tmp_path,draft["draft_id"])
    assert not client.calls
    for operation,params in [("connectapi",{}),("add_weight",{"weight":float("nan"),"timestamp":STAMP}),
        ("add_weight",{"weight":-1,"timestamp":STAMP}),("add_weight",{"weight":70}),
        ("send_workout_to_device",{"workout_id":1}),
        ("schedule_workout",{"workout_id":1,"date_str":"2026-02-30"}),
        ("upload_activity_file",{"activity_path":"secret.txt"})]:
        with pytest.raises((ValueError,TypeError)): validate(operation,params)


def test_ambiguous_batch_records_partial_progress_without_retry(tmp_path):
    service=WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare("create_training_calendar",CASES["create_training_calendar"],"partial-test")
    client=FakeClient(fail="schedule_workout")
    result=execute(client,tmp_path,draft["draft_id"])
    assert result["status"] == "unknown"
    assert result["steps"] == [{"index":0,"created_workout_id":"123"}]
    assert execute(client,tmp_path,draft["draft_id"]) == result
    assert len(client.calls) == 2


def test_xml_entities_and_non_activity_formats_rejected():
    for xml in (b'<!DOCTYPE gpx [<!ENTITY x SYSTEM "file:///secret">]><gpx>&x;</gpx>',b'<html/>'):
        with pytest.raises(Exception):
            validate("upload_activity_file",{"format":"gpx","content_base64":base64.b64encode(xml).decode()})


@pytest.mark.parametrize("operation", ["create_workout", "create_training_calendar"])
@pytest.mark.parametrize("defect", ["missing_ids", "nested_condition_value", "missing_distance", "invalid_repeat"])
def test_invalid_workouts_rejected_before_preparation(tmp_path, operation, defect):
    workout = json.loads(json.dumps(WORKOUT))
    step = workout["workoutSegments"][0]["workoutSteps"][0]
    if defect == "missing_ids":
        workout["sportType"].pop("sportTypeId")
    elif defect == "nested_condition_value":
        step["endCondition"]["conditionValue"] = step.pop("endConditionValue")
    elif defect == "missing_distance":
        step.pop("endConditionValue")
    else:
        workout["workoutSegments"][0]["workoutSteps"] = [{"type":"RepeatGroupDTO",
            "stepOrder":1,"stepType":{"stepTypeId":6,"stepTypeKey":"repeat"},
            "numberOfIterations":3,"workoutSteps":[{"type":"ExecutableStepDTO"}]}]
    params = {"workout_json":workout} if operation == "create_workout" else {
        "workouts":[{"date":"2026-10-12","workout":workout}]}
    service = WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    with pytest.raises(ValueError): service.prepare(operation,params,"invalid-workout-test")
    assert not service.store.exists()


def test_write_failure_reports_safe_category_and_is_not_retried(tmp_path):
    class Rejected(FakeClient):
        def upload_workout(self, **kwargs):
            self.calls.append("upload_workout")
            raise RuntimeError("HTTP 400: secret-token private-payload https://private.example")
    service = WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    draft = service.prepare("create_workout",CASES["create_workout"],"rejected-workout")
    client = Rejected()
    result = execute(client,tmp_path,draft["draft_id"])
    assert result["status"] == "unknown"
    assert result["error"]["code"] == "INVALID_REQUEST"
    assert not any(value in json.dumps(result) for value in ("secret-token","private-payload","private.example"))
    assert execute(client,tmp_path,draft["draft_id"]) == result
    assert len(client.calls) == 1


@pytest.mark.parametrize("workout_id", [123, "123"])
def test_schedule_uses_sdk_arguments_and_payload_without_network(tmp_path, workout_id):
    from garminconnect import Garmin
    service = WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    draft = service.prepare("schedule_workout",{"workout_id":workout_id,"date_str":"2026-10-12"},"schedule-valid")
    assert draft["status"] == "prepared"
    calls = []
    class Transport:
        def post(self, *args, **kwargs):
            calls.append((args,kwargs))
            return {"workoutId":123}
    client = Garmin()
    client.client = Transport()
    result = execute(client,tmp_path,draft["draft_id"])
    assert result["status"] == "completed"
    assert len(calls) == 1
    assert calls[0][0][1].endswith("/123")
    assert calls[0][1]["json"] == {"date":"2026-10-12"}


@pytest.mark.parametrize("parameters,expected", [
    ({"workout_id":123,"date":"2026-10-12"}, "exactly workout_id and date_str"),
    ({"workoutId":123,"date_str":"2026-10-12"}, "exactly workout_id and date_str"),
    ({"workout_id":True,"date_str":"2026-10-12"}, "positive integer"),
    ({"workout_id":123.0,"date_str":"2026-10-12"}, "positive integer"),
    ({"workout_id":"private-id-value","date_str":"2026-10-12"}, "positive integer"),
    ({"workout_id":123,"date_str":"20261012"}, "YYYY-MM-DD"),
    ({"workout_id":123,"date_str":"2026-02-30"}, "YYYY-MM-DD"),
    ({"workout_id":123,"date_str":None}, "YYYY-MM-DD"),
])
def test_schedule_input_errors_are_specific_and_do_not_create_draft(tmp_path, parameters, expected):
    from garmin_connect_mcp.server import safe_call
    service = WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    result = safe_call(service.prepare,"schedule_workout",parameters,"schedule-invalid")
    assert result["error"]["code"] == "INVALID_WRITE_INPUT"
    assert result["error"]["stage"] == "validation"
    assert result["error"]["garmin_request_sent"] is False
    assert expected in result["error"]["message"]
    assert "private-id-value" not in json.dumps(result)
    assert not service.store.exists()
