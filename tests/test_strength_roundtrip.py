"""Lossless completed-strength replacement regressions; synthetic account data."""
import copy
import json

import pytest
from garminconnect import Garmin
from garmin_connect_mcp.writes import validate, WriteInputError


def template():
    rows = []
    for i in range(26):
        row = dict(messageIndex=i, startTime=f"2026-01-01T12:{i:02}:00.0",
                   duration=60.0, repetitionCount=None, weight=None, setType="REST",
                   exercises=[], wktStepIndex=None, exerciseSetUUID=f"synthetic-{i}")
        row.update({f"recordedMetric{j}": None for j in range(40)})
        if i in (0, 2, 4):
            row.update(setType="ACTIVE", repetitionCount=10, weight=15875.0,
                       exercises=[dict(category="LUNGE", name="DUMBBELL_BULGARIAN_SPLIT_SQUAT", probability=99.609375)])
        if i in (18, 20, 22):
            row.update(setType="ACTIVE", repetitionCount=20, weight=20437.0,
                       exercises=[dict(category="CALF_RAISE", name="STANDING_CALF_RAISE", probability=99.609375)])
        if i == 25:
            row.update(setType="ACTIVE", repetitionCount=0,
                       exercises=[dict(category="UNKNOWN", name=None, probability=99.609375)])
        rows.append(row)
    return dict(activity_id="123", payload=dict(activityId=123, exerciseSets=rows))


def test_complete_template_roundtrip_and_six_corrections():
    original = template()
    assert len(json.dumps(original)) > 12000
    assert validate("replace_strength_sets", original) == original
    changed = copy.deepcopy(original)
    for i in (0, 2, 4):
        changed["payload"]["exerciseSets"][i]["weight"] = 31750.0
    for i in (18, 20, 22):
        changed["payload"]["exerciseSets"][i]["exercises"][0]["name"] = "SEATED_CALF_RAISE"
    assert validate("replace_strength_sets", changed) == changed
    restored = copy.deepcopy(changed)
    for i in (0, 2, 4, 18, 20, 22):
        restored["payload"]["exerciseSets"][i] = original["payload"]["exerciseSets"][i]
    assert restored == original
    assert len(changed["payload"]["exerciseSets"]) == 26


@pytest.mark.parametrize("exercises", [[], [dict(category="UNKNOWN", name=None)], [dict(category="CALF_RAISE", name=None)]])
def test_empty_unknown_parent_only_zero_rep_sets(exercises):
    parameters = template()
    parameters["payload"]["exerciseSets"][-1]["exercises"] = exercises
    assert validate("replace_strength_sets", parameters) == parameters


@pytest.mark.parametrize("field,value", [("category", "MADE_UP"), ("name", "MADE_UP"), ("category", []), ("name", {})])
def test_invalid_catalog_field_has_exact_path(field, value):
    parameters = template()
    parameters["payload"]["exerciseSets"][0]["exercises"][0][field] = value
    with pytest.raises(WriteInputError, match=rf"exerciseSets\[0\].exercises\[0\].{field}"):
        validate("replace_strength_sets", parameters)


def test_sdk_sends_full_body_without_conversion_or_field_loss():
    parameters = validate("replace_strength_sets", template())
    class Transport:
        def put(self, domain, url, **kwargs):
            assert domain == "connectapi"
            assert url.endswith("/123/exerciseSets")
            assert kwargs == dict(json=parameters["payload"], api=True)
            return kwargs["json"]
    client = Garmin()
    client.client = Transport()
    assert client.set_activity_exercise_sets(**parameters) == parameters["payload"]


def test_strength_payload_limit_reports_specific_error():
    parameters = template()
    parameters["payload"]["metadata"] = "x" * (2 * 1024 * 1024)
    with pytest.raises(WriteInputError, match="parameters: payload exceeds 2097152 bytes"):
        validate("replace_strength_sets", parameters)


def test_historical_exercise_requires_exact_fresh_target_match():
    parameters = template()
    parameters["payload"]["exerciseSets"][0]["exercises"][0]["name"] = "HISTORICAL_VARIANT"
    original = copy.deepcopy(parameters["payload"])
    parameters["payload"]["exerciseSets"][0]["weight"] = 31750
    assert validate("replace_strength_sets", parameters, strength_original=original) == parameters
    with pytest.raises(WriteInputError):
        validate("replace_strength_sets", parameters)
    parameters["payload"]["exerciseSets"][0]["exercises"][0]["name"] = "INVENTED_NEW_VARIANT"
    with pytest.raises(WriteInputError):
        validate("replace_strength_sets", parameters, strength_original=original)


def test_prepare_preserves_complete_payload(tmp_path):
    from garmin_connect_mcp.writes import WriteService
    parameters = template()
    preview = WriteService(tmp_path).prepare("replace_strength_sets", parameters, "full-roundtrip-test")
    assert preview["parameters"] == parameters


def test_guarded_commit_preserves_historical_and_metadata(tmp_path):
    from garmin_connect_mcp.writes import WriteService, execute
    parameters = template()
    parameters["payload"]["exerciseSets"][6]["exercises"] = [dict(category="LEGACY_CATEGORY", name="LEGACY_NAME", probability=99.0)]
    original = copy.deepcopy(parameters["payload"])
    parameters["payload"]["exerciseSets"][0]["weight"] = 31750
    class Client:
        writes = 0
        def get_activity(self, activity_id):
            return dict(activityId=123)
        def get_activity_exercise_sets(self, activity_id):
            return original
        def set_activity_exercise_sets(self, activity_id, payload):
            self.writes += 1
            assert payload == parameters["payload"]
            return dict(activityId=123)
    service = WriteService(tmp_path)
    draft = service.prepare("replace_strength_sets", parameters, "historical-commit-test", strength_original=original)
    client = Client()
    assert execute(client, tmp_path, draft["draft_id"])["status"] == "completed"
    assert execute(client, tmp_path, draft["draft_id"])["status"] == "completed"
    assert client.writes == 1
