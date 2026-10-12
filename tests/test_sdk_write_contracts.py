"""Run every exposed SDK write without network; mocks implement actual response semantics."""
import base64
import inspect
import json
from pathlib import Path

import pytest
from garminconnect import Garmin
from garmin_connect_mcp.writes import WriteService,execute,METHODS,validate
from garmin_connect_mcp.write_contracts import SCHEMAS,contract
from garmin_connect_mcp.server import safe_call
from test_writes import CASES,WORKOUT


class Response:
    status_code=200
    def json(self): return {"workoutId":123,"activityId":456,"samplePk":789}


class Transport:
    def __init__(self): self.calls=[]
    def request(self,method,domain,path,**kwargs):
        captured=dict(kwargs)
        if "files" in captured:
            value=captured["files"]["file"][1]
            captured["file_bytes"]=value.read() if hasattr(value,"read") else value
        self.calls.append((method,path,captured))
        return Response().json() if kwargs.get("api") else Response()
    def post(self,domain,path,**kwargs): return self.request("POST",domain,path,**kwargs)
    def put(self,domain,path,**kwargs): return self.request("PUT",domain,path,**kwargs)
    def delete(self,domain,path,**kwargs): return self.request("DELETE",domain,path,**kwargs)
    def connectapi(self,path,**kwargs):
        if "calendar" in path: return {"calendarItems":[]}
        if "devices" in path: return [{"deviceId":3}]
        if "activityTypes" in path: return [{"typeId":1,"typeKey":"running","parentTypeId":17}]
        if "exerciseSets" in path: return {"exerciseSets":[]}
        if "activity-service/activity/" in path: return {"activityId":456}
        return {"workoutId":123,"workoutName":"Synthetic","workoutSegments":[]} if "workout" in path else []


@pytest.mark.parametrize("operation",list(CASES))
def test_real_sdk_write_reaches_expected_transport_once(tmp_path,operation):
    service=WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare(operation,CASES[operation],"sdk-contract-test")
    client=Garmin()
    client.client=Transport()
    result=execute(client,tmp_path,draft["draft_id"])
    assert result["status"]=="completed",result
    expected=2 if operation=="create_training_calendar" else 1
    assert len(client.client.calls)==expected
    assert execute(client,tmp_path,draft["draft_id"])==result
    assert len(client.client.calls)==expected
    if operation=="create_manual_activity":
        body=client.client.calls[0][2]["json"]
        assert body["summaryDTO"]["distance"]==5000
        assert body["summaryDTO"]["duration"]==1800
        assert body["accessControlRuleDTO"]["typeKey"]=="private"
    if operation=="add_body_composition":
        data=client.client.calls[0][2]["file_bytes"]
        assert data[8:12]==b".FIT"


def test_schemas_match_sdk_signature_names_and_required_arguments():
    assert set(SCHEMAS)==set(CASES)
    for operation,method in METHODS.items():
        if operation=="upload_activity_file": continue  # MCP translates base64 into an isolated temp path.
        signature=inspect.signature(getattr(Garmin,method))
        fields=set(SCHEMAS[operation]["properties"])
        assert fields==set(signature.parameters)-{"self"}
        required={k for k,v in signature.parameters.items() if k!="self" and v.default is inspect.Parameter.empty}
        assert required<=set(SCHEMAS[operation]["required"])
        assert contract(operation)["garmin_request_sent"] is False


@pytest.mark.parametrize("operation",list(CASES))
def test_all_operation_bad_arguments_return_local_errors(tmp_path,operation):
    service=WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    result=safe_call(service.prepare,operation,{"private_token_value":"do-not-return"},"invalid-all-test")
    assert result["error"]["code"]=="INVALID_WRITE_INPUT"
    assert result["error"]["garmin_request_sent"] is False
    assert "do-not-return" not in json.dumps(result)
    assert not service.store.exists()


@pytest.mark.parametrize("operation,parameters",[
    ("add_hydration",{"value_in_ml":250,"timestamp":"2026-10-12T12:00:00+00:00","cdate":"2026-10-11"}),
    ("add_body_composition",{"weight":700,"timestamp":"2026-10-11T12:00:00Z"}),
    ("add_body_composition",{"weight":70,"metabolic_age":300,"timestamp":"2026-10-11T12:00:00Z"}),
    ("add_blood_pressure",{"systolic":80,"diastolic":100,"timestamp":"2026-10-11T12:00:00Z"}),
    ("create_manual_activity",{**CASES["create_manual_activity"],"start_datetime":"2026-03-08T02:30:00","time_zone":"America/Los_Angeles"}),
    ("create_manual_activity",{**CASES["create_manual_activity"],"start_datetime":"2026-11-01T01:30:00","time_zone":"America/Los_Angeles"}),
    ("create_manual_activity",{**CASES["create_manual_activity"],"start_datetime":"2026-10-11T12:00:00Z"}),
    ("replace_strength_sets",{"activity_id":1,"payload":{"exerciseSets":[{"exercises":[{"category":"MADE_UP","name":"NOPE"}]}]}}),
])
def test_cross_field_and_encoding_guardrails(operation,parameters):
    with pytest.raises(ValueError): validate(operation,parameters)


def test_partial_import_cannot_be_reported_as_completed(tmp_path):
    class Rejected:
        def upload_activity(self,path):
            return {"detailedImportResult":{"successes":[{"internalId":123}],"failures":[{}]}}
    service=WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled":True}))
    draft=service.prepare("upload_activity_file",CASES["upload_activity_file"],"partial-import")
    result=execute(Rejected(),tmp_path,draft["draft_id"])
    assert result["status"]=="unknown"
    assert result["error"]["code"]=="IMPORT_REJECTED_OR_PARTIAL"
    assert result["result"]["internalId"]==["123"]


def test_fit_checksum_and_length_validation():
    from scripts.audit_fixtures import fit_activity
    content=fit_activity()
    parameters={"format":"fit","content_base64":base64.b64encode(content).decode()}
    assert validate("upload_activity_file",parameters)==parameters
    corrupted=bytearray(content); corrupted[-1]^=1
    with pytest.raises(ValueError): validate("upload_activity_file",{**parameters,"content_base64":base64.b64encode(corrupted).decode()})
