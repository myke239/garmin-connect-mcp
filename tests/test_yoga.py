import asyncio
import copy
import json
import pytest
from garmin_connect_mcp.yoga import POSES, pose_step
from garmin_connect_mcp.workout_discovery import exercises
from garmin_connect_mcp.sport_schemas import build_workout
from garmin_connect_mcp.writes import validate, WriteInputError
from garmin_connect_mcp.server import create_server


def template(key="CHILDS"):
    built=pose_step(key,30,1)
    return build_workout("yoga","Synthetic yoga",workout_segments=[{"segmentOrder":1,"sportType":built["sportType"],"workoutSteps":[built["step"]]}])["workout_json"]


def test_catalog_pagination_is_complete_and_no_pose_enters_strength_builder():
    from garmin_connect_mcp.workout_discovery import strength_step
    first=exercises(category="POSE",limit=50)
    second=exercises(category="POSE",limit=50,start=first["next_start"])
    assert first["total_matches"]==85 and second["next_start"] is None
    assert {r["exercise"] for r in first["exercises"]+second["exercises"]}==POSES
    assert exercises("CHILDS",category="POSE")["exact_matches"][0]["exercise"]=="CHILDS"
    with pytest.raises(WriteInputError): strength_step("POSE","CHILDS",1,1)


@pytest.mark.parametrize("key",sorted(POSES))
def test_every_verified_pose_passes_create_update_calendar_contracts(key):
    payload=template(key)
    validate("create_workout",{"workout_json":payload})
    validate("update_workout",{"workout_id":"123","workout_json":payload})
    validate("create_training_calendar",{"workouts":[{"date":"2026-10-20","workout":payload}]})
    assert payload["workoutSegments"][0]["workoutSteps"][0]["exerciseName"]==key


@pytest.mark.parametrize("field,value",[("exerciseName","MADE_UP"),("exerciseName",None),("endConditionValue",True),("endConditionValue",0),("endConditionValue",30.5),("endConditionValue",86401),("weightValue",100),("targetValueOne",1),("secondaryTargetType",{})])
def test_invalid_pose_fields_rejected_before_write(field,value):
    payload=template();payload["workoutSegments"][0]["workoutSteps"][0][field]=value
    with pytest.raises(WriteInputError): validate("create_workout",{"workout_json":payload})


def test_wrong_sport_and_rep_condition_are_rejected():
    payload=template()
    payload["sportType"]=payload["workoutSegments"][0]["sportType"]={"sportTypeId":5,"sportTypeKey":"strength_training"}
    with pytest.raises(WriteInputError): validate("create_workout",{"workout_json":payload})
    payload=template();payload["workoutSegments"][0]["workoutSteps"][0]["endCondition"]={"conditionTypeId":10,"conditionTypeKey":"reps"}
    with pytest.raises(WriteInputError): validate("create_workout",{"workout_json":payload})


@pytest.mark.parametrize("key,duration,order",[("MADE_UP",30,1),("CHILDS",True,1),("CHILDS",30.5,1),("CHILDS",30,101)])
def test_builder_bounds(key,duration,order):
    with pytest.raises(WriteInputError): pose_step(key,duration,order)


def test_yoga_tools_work_without_auth_and_are_readonly():
    async def run():
        server=create_server()
        tool=next(t for t in await server.list_tools() if t.name=="build_garmin_yoga_step")
        assert tool.annotations.readOnlyHint
        blocks=await server.call_tool(tool.name,{"exercise":"CHILDS","duration_seconds":30,"step_order":1})
        blocks=blocks[0] if isinstance(blocks,tuple) else blocks
        assert json.loads(blocks[0].text)["step"]["category"]=="POSE"
    asyncio.run(run())
