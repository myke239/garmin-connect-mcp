"""Synthetic executable-program acceptance; never calls a Garmin account."""
import asyncio
import copy
import json

import pytest
from garminconnect.workout import create_repeat_group, create_strength_exercise_step, PaceTarget

from garmin_connect_mcp.builders import strength_workout, running_workout, swim_workout
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.lifecycle import template
from garmin_connect_mcp.writes import WriteService, WriteInputError, execute, validate


def rows(result):
    return result["workout_json"]["workoutSegments"][0]["workoutSteps"]


def expand(steps):
    """Independent execution oracle: recursively interpret repetitions and last-rest skip."""
    result = []
    for item in steps:
        if item["type"] == "RepeatGroupDTO":
            for index in range(item["numberOfIterations"]):
                children = item["workoutSteps"]
                if index == item["numberOfIterations"] - 1 and item.get("skipLastRestStep"):
                    children = children[:-1]
                result.extend(expand(children))
        else:
            result.append(item)
    return result


def squat(**kwargs):
    return {"name": "Squat", "sets": 3, "reps": 10, **kwargs}


def test_strength_repeat_transition_and_no_trailing_rest():
    result = strength_workout("Two exercises", [squat(), {"name": "Leg press", "sets": 3, "reps": 8}])
    first, transition, last = rows(result)
    assert first["type"] == last["type"] == "RepeatGroupDTO"
    assert first["numberOfIterations"] == last["numberOfIterations"] == 3
    assert first["skipLastRestStep"] is last["skipLastRestStep"] is True
    assert first["endCondition"] == create_repeat_group(3, [], 1).model_dump()["endCondition"]
    active, rest = first["workoutSteps"]
    sdk = create_strength_exercise_step("SQUAT", 2, 10, "SQUAT").model_dump(exclude_none=True, mode="json")
    assert all(active[k] == value for k, value in sdk.items())
    assert active["childStepId"] == rest["childStepId"] == first["childStepId"]
    assert rest["endConditionValue"] == 60
    assert transition["endConditionValue"] == 120
    actual = expand(rows(result))
    assert [s["endConditionValue"] for s in actual] == [10,60,10,60,10,120,8,60,8,60,8]
    assert actual[-1]["stepType"]["stepTypeKey"] == "interval"
    assert result["duration_estimate"]["programmed_seconds"] == 360
    assert result["duration_estimate"]["total_seconds"] is None
    assert result["watch_execution_verified"] is False


def test_handstand_exact_ten_minutes_including_last_recovery_then_transition():
    result = strength_workout("Skill and strength", [{"name": "Wall Handstand Hold", "sets": 10,
        "duration_seconds": 20, "rest_seconds": 40, "include_final_rest": True,
        "notes": "Maintain straight arms and controlled alignment."}, squat()])
    group, transition, _ = rows(result)
    hold, rest = group["workoutSteps"]
    assert group["numberOfIterations"] == 10 and group["skipLastRestStep"] is False
    assert hold["endCondition"] == {"conditionTypeId": 2, "conditionTypeKey": "time"}
    assert hold["endConditionValue"] == 20 and rest["endConditionValue"] == 40
    assert "category" not in hold and "exerciseName" not in hold
    assert hold["description"] == "Wall Handstand Hold — Maintain straight arms and controlled alignment."
    assert sum(s["endConditionValue"] for s in expand([group])) == 600
    assert transition["endConditionValue"] == 120
    assert result["warnings"] and result["preview"][0]["catalog_resolved"] is False


@pytest.mark.parametrize("include_final,expected", [(False,560),(True,600)])
def test_last_timed_exercise_respects_explicit_final_recovery(include_final, expected):
    result = strength_workout("Skill", [{"name":"Wall Handstand Hold", "sets":10,
        "duration_seconds":20, "rest_seconds":40, "include_final_rest":include_final}])
    assert len(rows(result)) == 1
    assert result["workout_json"]["estimatedDurationInSecs"] == expected
    assert result["duration_estimate"]["total_seconds"] == expected


def test_configurable_rest_zero_and_single_set():
    result = strength_workout("Custom rests", [squat(sets=1), squat(rest_seconds=30, transition_seconds=45), squat()],
        {"rest_between_sets_seconds":0, "rest_between_exercises_seconds":90})
    assert [s["endConditionValue"] for s in expand(rows(result))] == [10,90,10,30,10,30,10,45,10,10,10]
    assert rows(result)[0]["type"] == "RepeatGroupDTO"
    assert rows(result)[0]["skipLastRestStep"] is False


@pytest.mark.parametrize("change", [
    {"reps": True}, {"sets":100}, {"sets":1.5}, {"duration_seconds":20},
    {"include_final_rest":"false"}, {"rest_seconds":-1}, {"rest_seconds":float("inf")},
    {"transition_seconds":True}, {"extra":1}, {"name":"Bulgarian split squat"},
    {"category":"SQUAT", "exercise":"STEP_DOWN"},
])
def test_actionable_exercise_validation(change):
    with pytest.raises(WriteInputError, match=r"exercises\[0\]"):
        strength_workout("Invalid", [squat(**change)])


@pytest.mark.parametrize("defaults", [{"unknown":60}, {"rest_between_sets_seconds":True}, [], {"rest_between_exercises_seconds":-1}])
def test_invalid_defaults(defaults):
    with pytest.raises(WriteInputError, match="defaults"):
        strength_workout("Invalid", [squat()], defaults)


def test_tempo_program_has_separate_warmup_repeat_and_cooldown():
    result = running_workout("Tempo", [{"duration_seconds":300,"repeats":3,"recovery_seconds":180,"hr_zone":3}], 900, 1080)
    steps = rows(result)
    assert [s["type"] for s in steps] == ["ExecutableStepDTO","RepeatGroupDTO","ExecutableStepDTO"]
    assert [s["endConditionValue"] for s in expand(steps)] == [900,300,180,300,180,300,1080]
    assert result["duration_estimate"]["total_seconds"] == 3240  # The supplied example totals 54, not 55 minutes.
    assert steps[1]["workoutSteps"][0]["zoneNumber"] == 3
    assert steps[1]["workoutSteps"][1]["stepType"]["stepTypeKey"] == "recovery"


def test_running_final_recovery_and_sdk_pace_units():
    result = running_workout("Pace", [{"duration_seconds":300,"repeats":3,"recovery_seconds":60,
        "include_final_recovery":True,"pace_s_km":[300,360]}])
    group = rows(result)[0]
    target = group["workoutSteps"][0]
    sdk = PaceTarget(lower_limit=1000/360, upper_limit=1000/300)
    assert target["targetValueOne"] == sdk.lower_limit
    assert target["targetValueTwo"] == sdk.upper_limit
    assert group["skipLastRestStep"] is False
    assert result["duration_estimate"]["total_seconds"] == 1080


def test_swim_uses_same_sdk_pace_order_and_reversed_manual_targets_rejected():
    result = swim_workout("Pool pace", 25, [{"distance_m":100,"pace_s_100m":[90,120]}])
    interval = rows(result)[0]
    assert interval["targetValueOne"] == pytest.approx(100/120)
    assert interval["targetValueTwo"] == pytest.approx(100/90)
    interval["targetValueOne"], interval["targetValueTwo"] = interval["targetValueTwo"], interval["targetValueOne"]
    with pytest.raises(WriteInputError, match=r"workoutSteps\[0\].*metres/second"):
        validate("create_workout", {"workout_json":result["workout_json"]})


@pytest.mark.parametrize("defect", ["order", "duplicate_group", "boolean_child"])
def test_group_identity_and_execution_order_rejected(defect):
    result = strength_workout("Two groups", [squat(), squat()])
    first, transition, second = rows(result)
    if defect == "order":
        first["workoutSteps"][0]["stepOrder"], first["workoutSteps"][1]["stepOrder"] = 3, 2
    if defect == "duplicate_group":
        second["childStepId"] = first["childStepId"]
        for child in second["workoutSteps"]:
            child["childStepId"] = first["childStepId"]
    if defect == "boolean_child":
        first["workoutSteps"][0]["childStepId"] = True
    with pytest.raises(WriteInputError, match="workoutSteps"):
        validate("create_workout", {"workout_json":result["workout_json"]})


@pytest.mark.parametrize("defect", ["condition", "count", "skip", "order", "reference", "last_child", "segment"])
def test_malformed_nested_repeat_is_rejected_before_prepare(tmp_path, defect):
    workout = strength_workout("Nested", [squat()])["workout_json"]
    group = workout["workoutSegments"][0]["workoutSteps"][0]
    if defect == "condition": group["endCondition"]["conditionTypeId"] = 2
    if defect == "count": group["endConditionValue"] = 2
    if defect == "skip": group["skipLastRestStep"] = "true"
    if defect == "order": group["workoutSteps"][0]["stepOrder"] = 1
    if defect == "reference": group["workoutSteps"][0]["childStepId"] = 999
    if defect == "last_child": group["workoutSteps"].pop()
    if defect == "segment": workout["workoutSegments"][0]["segmentOrder"] = True
    with pytest.raises(ValueError):
        WriteService(tmp_path).prepare("create_workout", {"workout_json":workout}, "invalid-program")


def test_large_complete_template_fits_bounded_workout_limit():
    workout = strength_workout("Large", [squat(notes="x"*500) for _ in range(20)])["workout_json"]
    assert len(json.dumps(workout).encode("utf-8")) > 12000
    validate("create_workout", {"workout_json":workout})
    workout["workoutId"] = 123
    validate("update_workout", {"workout_id":123,"workout_json":workout})
    workout["extraMetadata"] = "x" * (256*1024)
    with pytest.raises(WriteInputError, match="262144 bytes"):
        validate("update_workout", {"workout_id":123,"workout_json":workout})


def test_mcp_declarative_builder_is_readonly_and_exposes_errors():
    async def check():
        server = create_server(tool_profile="all")
        tool = next(t for t in await server.list_tools() if t.name == "build_garmin_strength_workout")
        assert tool.annotations.readOnlyHint and "defaults" in tool.inputSchema["properties"]
        result = await server.call_tool(tool.name, {"workout_name":"MCP", "exercises":[squat()]})
        body = json.loads(result[0][0].text if isinstance(result, tuple) else result[0].text)
        assert rows(body)[0]["numberOfIterations"] == 3
        assert body["garmin_request_sent"] is False
        bad = await server.call_tool(tool.name, {"workout_name":"MCP", "exercises":[squat(reps=True)]})
        body = json.loads(bad[0][0].text if isinstance(bad, tuple) else bad[0].text)
        assert "exercises[0]" in body["error"]["message"]
    asyncio.run(check())


def test_scheduled_update_preserves_id_calendar_and_unrelated_content(tmp_path):
    original = strength_workout("Scheduled", [squat(), {"name":"Leg press","sets":2,"reps":8}])["workout_json"]
    original.update(workoutId=123, description="Preserve these notes", ownerId=456,
        estimatedDurationInSecs=1800, customMetadata={"synthetic":"preserve"})
    calendar = {"calendarItems":[{"id":789,"workoutId":123,"itemType":"workout","date":"2026-10-28"}]}

    class Client:
        def __init__(self):
            self.saved = copy.deepcopy(original)
            self.updates = 0

        def get_workout_by_id(self, workout_id):
            assert str(workout_id) == "123"
            return copy.deepcopy(self.saved)

        def get_scheduled_workouts(self, year, month):
            return copy.deepcopy(calendar)

        def update_workout(self, workout_id, workout_json):
            assert str(workout_id) == "123"
            self.updates += 1
            self.saved = copy.deepcopy(workout_json)
            return copy.deepcopy(self.saved)

    client = Client()
    read_calls = []
    def read_runner(directory, method, args, kwargs):
        read_calls.append(method)
        return getattr(client, method)(*args, **kwargs)
    backend = GarminService(TokenStore(tmp_path), read_runner)
    server = create_server(adapter=backend, tool_profile="all")
    async def mcp_read(name, args):
        result = await server.call_tool(name, args)
        return json.loads(result[0][0].text if isinstance(result, tuple) else result[0].text)
    replacement = asyncio.run(mcp_read("get_workout_template", {"workout_id":"123"}))
    assert replacement == original  # No dropped metadata, estimates or identifiers.
    before_calendar = asyncio.run(mcp_read("list_scheduled_workouts", {"year":2026,"month":10}))
    # Populate the pre-mutation template cache explicitly.
    backend.call("get_workout_by_id", "123")
    replacement["workoutSegments"][0]["workoutSteps"][0]["workoutSteps"][0]["endConditionValue"] = 12
    service = WriteService(tmp_path, runner=lambda directory, method, args, kwargs: execute(client, directory, *args, **kwargs))
    draft = service.prepare("update_workout", {"workout_id":123,"workout_json":replacement}, "scheduled-edit")
    context = {k:v for k,v in draft["commit_arguments"].items() if k != "draft_id"}
    result = service.commit_reviewed(draft["draft_id"], "update_workout", context)
    assert result["status"] == "completed"
    readback = asyncio.run(mcp_read("get_workout_template", {"workout_id":"123"}))
    assert readback == replacement
    assert readback["workoutSegments"][0]["workoutSteps"][1:] == original["workoutSegments"][0]["workoutSteps"][1:]
    after_calendar = asyncio.run(mcp_read("list_scheduled_workouts", {"year":2026,"month":10}))
    assert after_calendar["scheduled_workouts"] == before_calendar["scheduled_workouts"] == calendar["calendarItems"]
    assert before_calendar["cached"] is after_calendar["cached"] is False
    assert read_calls.count("get_workout_by_id") == 3
    assert read_calls.count("get_scheduled_workouts") == 2
    assert service.commit_reviewed(draft["draft_id"], "update_workout", context) == result
    assert client.updates == 1


@pytest.mark.parametrize("raw", [{"workoutId":456}, {"workoutId":123,"description":"x"*(256*1024)}])
def test_full_template_never_returns_wrong_identity_or_truncated_content(raw):
    class Backend:
        def fresh_call(self, *args):
            return raw
    with pytest.raises(WriteInputError):
        template(Backend(), "123")
