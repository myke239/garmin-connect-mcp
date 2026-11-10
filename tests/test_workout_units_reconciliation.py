"""Regression fixtures from user-reported Connect display; no live account writes."""
import copy
import json

import pytest

from garmin_connect_mcp.builders import running_workout
from garmin_connect_mcp.workout_quality import compare_workout, quality_warnings
from garmin_connect_mcp.writes import WriteService, execute, validate


def workout():
    return running_workout("14-mile easy run", [{"distance_miles":14, "pace_min_mile":["9:15", "11:30"]}])["workout_json"]


def step(value):
    return value["workoutSegments"][0]["workoutSteps"][0]


def test_distance_and_pace_are_independent_and_use_connect_units():
    value = workout()
    active = step(value)
    assert active["endCondition"] == {"conditionTypeId":3, "conditionTypeKey":"distance"}
    assert active["endConditionValue"] == pytest.approx(22530.816)
    assert active["targetValueOne"] == pytest.approx(2.899718919)
    assert active["targetValueTwo"] == pytest.approx(2.332382609)
    assert active["targetType"] == {"workoutTargetTypeId":6, "workoutTargetTypeKey":"pace.zone"}
    assert "targetValueThree" not in active
    assert value["estimatedDurationInSecs"] == 0


@pytest.mark.parametrize("interval", [
    {"distance_miles":14, "pace_min_mile":["11:30","9:15"]},
    {"distance_miles":14, "pace_min_mile":["9:60","11:30"]},
    {"distance_miles":14, "pace_min_mile":["0:15","11:30"]},
    {"distance_miles":14, "pace_min_mile":[555,690]},
    {"distance_miles":14, "pace_min_mile":["9:15","9:15"]},
    {"distance_miles":14, "distance_m":100},
    {"distance_miles":14, "duration_seconds":3600},
    {"distance_miles":True}, {"distance_miles":float("inf")},
    {"distance_miles":14, "pace_s_km":[300,360], "pace_min_mile":["9:15","11:30"]},
    {"distance_miles":14, "hr_zone":2, "pace_min_mile":["9:15","11:30"]},
])
def test_bad_units_or_ambiguous_end_conditions_rejected(interval):
    with pytest.raises(ValueError):
        running_workout("Invalid", [interval])


@pytest.mark.parametrize("change", [{"targetValueOne":1}, {"targetValueTwo":0},
    {"targetValueOne":None}, {"targetValueTwo":float("inf")}, {"endConditionValue":0}])
def test_full_payload_validates_both_end_condition_and_pace(change):
    value = workout()
    step(value).update(change)
    with pytest.raises(ValueError):
        validate("create_workout", {"workout_json":value})


def test_quality_warns_without_rewriting_notes(tmp_path):
    value = workout()
    value["description"] = "Approximate time-based workout"
    step(value)["description"] = "time based run"
    assert len(quality_warnings(value)) == 2
    draft = WriteService(tmp_path).prepare("create_workout", {"workout_json":value}, "quality-test-key")
    assert len(draft["quality_warnings"]) == 2
    assert draft["parameters"]["workout_json"]["description"] == value["description"]


def test_readback_ignores_server_metadata_but_detects_removed_targets():
    expected = workout()
    actual = copy.deepcopy(expected)
    actual.update(workoutId=123, updatedDate="synthetic")
    step(actual).update(stepId=456)
    assert compare_workout(expected, actual)["state"] == "verified"
    step(expected).pop("targetValueOne")
    assert compare_workout(expected, actual)["mismatch_paths"] == ["workout.workoutSegments[0].workoutSteps[0].targetValueOne"]


class Client:
    def __init__(self):
        self.saved = {str(i): dict(workout(), workoutId=i) for i in (123,124)}
        for value in self.saved.values():
            step(value)["targetValueOne"] = 3.1
        self.writes = []
        self.fail_after_write = False

    def get_workout_by_id(self, workout_id):
        return copy.deepcopy(self.saved[str(workout_id)])

    def fresh_call(self, method, workout_id):
        assert method == "get_workout_by_id"
        return self.get_workout_by_id(workout_id)

    def update_workout(self, workout_id, workout_json):
        self.writes.append(str(workout_id))
        self.saved[str(workout_id)] = copy.deepcopy(workout_json)
        if self.fail_after_write:
            raise TimeoutError("synthetic lost response")
        return self.saved[str(workout_id)]


def test_interrupted_batch_ledger_reconciles_each_id_and_never_replays(tmp_path):
    service, client = WriteService(tmp_path), Client()
    drafts = [service.prepare("update_workout", {"workout_id":i,
        "workout_json":dict(workout(), workoutId=i)}, f"batch-intent-{i}") for i in (123,124)]
    assert execute(client, tmp_path, drafts[0]["draft_id"])["verification"]["state"] == "verified"
    client.fail_after_write = True
    assert execute(client, tmp_path, drafts[1]["draft_id"])["status"] == "unknown"
    for draft in drafts:
        status = service.reconcile_workout(draft["draft_id"], client)
        assert status["verification"]["next_action"] == "skip_already_applied"
        assert status["verification"]["app_display_verified"] is False
        assert status["verification"]["watch_execution_verified"] is False
        assert "parameters" not in status
        execute(client, tmp_path, draft["draft_id"])
    assert client.writes == ["123", "124"]
    ledger = json.loads(service.store.load())
    assert {d["verification"]["workout_id"] for d in ledger.values()} == {"123","124"}
    assert {d["status"] for d in ledger.values()} == {"completed","unknown"}


def test_already_matching_prepared_update_is_skipped_and_mismatch_is_reported(tmp_path):
    service, client = WriteService(tmp_path), Client()
    value = client.get_workout_by_id(123)
    draft = service.prepare("update_workout", {"workout_id":123, "workout_json":value}, "already-applied-intent")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["result"]["skipped_already_applied"] and not client.writes
    step(client.saved["123"])["endConditionValue"] = 100
    result = service.reconcile_workout(draft["draft_id"], client)
    assert result["verification"]["state"] == "mismatch"
    assert result["status"] == "completed"  # Transport status is not rewritten as readback status.
    assert result["verification"]["calendar_association_verified"] is False


def test_metadata_only_update_is_not_silently_skipped(tmp_path):
    service, client = WriteService(tmp_path), Client()
    expected = client.get_workout_by_id(123)
    expected["customMetadata"] = {"planned": "updated"}
    expected["estimatedDurationInSecs"] = 6000
    expected["description"] = None
    draft = service.prepare("update_workout", {"workout_id":123, "workout_json":expected}, "metadata-update-intent")
    result = execute(client, tmp_path, draft["draft_id"])
    assert client.writes == ["123"]
    assert result["verification"]["state"] == "verified"
    assert client.saved["123"]["customMetadata"] == {"planned":"updated"}


def test_mcp_status_reconciles_without_exposing_payload_or_writing(tmp_path):
    import asyncio
    from garmin_connect_mcp.auth import TokenStore
    from garmin_connect_mcp.service import GarminService
    from garmin_connect_mcp.server import create_server
    client = Client()
    service = WriteService(tmp_path)
    draft = service.prepare("update_workout", {"workout_id":123, "workout_json":client.get_workout_by_id(123)}, "mcp-reconcile-intent")
    backend = GarminService(TokenStore(tmp_path), lambda directory, method, args, kwargs: getattr(client, method)(*args, **kwargs))
    server = create_server(adapter=backend, tool_profile="all")
    async def check():
        tool = next(t for t in await server.list_tools() if t.name == "get_garmin_write_status")
        assert tool.annotations.readOnlyHint and "reconcile_workout" in tool.inputSchema["properties"]
        result = await server.call_tool(tool.name, {"draft_id":draft["draft_id"], "reconcile_workout":True})
        blocks = result[0] if isinstance(result, tuple) else result
        body = json.loads(blocks[0].text)
        assert body["verification"]["state"] == "verified"
        assert body["status"] == "prepared" and "parameters" not in body
    asyncio.run(check())
    assert not client.writes
