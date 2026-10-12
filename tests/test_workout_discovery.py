import asyncio
import json
import pytest
from garminconnect.workout import create_strength_exercise_step
from garmin_connect_mcp.workout_discovery import exercises,strength_step,workout_schema
from garmin_connect_mcp.writes import validate
from garmin_connect_mcp.server import create_server


@pytest.mark.parametrize("term,category,exercise",[
    ("Leg Press","SQUAT","LEG_PRESS"),("leg presses","SQUAT","LEG_PRESS"),
    ("standing_calf_raise","CALF_RAISE","STANDING_CALF_RAISE"),
    ("Standing Calf Raises","CALF_RAISE","STANDING_CALF_RAISE"),
    ("SQUAT / LEG_PRESS","SQUAT","LEG_PRESS"),
])
def test_exact_movement_discovery_preserves_enum_pair(term,category,exercise):
    result=exercises(term)
    assert result["match_status"]=="exact"
    assert len(result["exact_matches"])==1
    assert result["exact_matches"][0]["category"]==category
    assert result["exact_matches"][0]["exercise"]==exercise
    assert result["selection_required"] is False


def test_bulgarian_variants_are_not_selected_for_user():
    result=exercises("Bulgarian split squats")
    assert result["total_matches"]==4
    assert result["exact_matches"]==[]
    assert result["selection_required"] is True
    assert all(row["category"]=="LUNGE" for row in result["exercises"])


def test_missing_step_down_does_not_become_step_up_or_parent_category():
    result=exercises("step-downs")
    assert result["match_status"]=="not_found"
    assert result["exercises"]==[]
    assert result["selection_required"] is True
    with pytest.raises(ValueError):strength_step("LUNGE","STEP_DOWN",10,1)


def test_catalog_pagination_and_category_filter():
    first=exercises("",limit=3,category="CALF_RAISE")
    assert first["next_start"]==3
    second=exercises("",limit=3,start=3,category="CALF_RAISE")
    assert first["exercises"]!=second["exercises"]
    assert all(row["category"]=="CALF_RAISE" for row in first["exercises"]+second["exercises"])


def test_strength_header_reps_and_load_units_match_sdk():
    schema=workout_schema("strength_training")
    assert schema["sportType"]["sportTypeId"]==5
    assert schema["reps_condition"]["conditionTypeId"]==10
    result=strength_step("SQUAT","LEG_PRESS",8,2,25)
    assert result["step"]==create_strength_exercise_step(category="SQUAT",exercise_name="LEG_PRESS",reps=8,step_order=2,weight_kg=25).model_dump(exclude_none=True,mode="json")
    assert result["step"]["weightValue"]==25000
    assert result["garmin_request_sent"] is False
    payload={"workoutName":"Synthetic strength example","sportType":schema["sportType"],
        "workoutSegments":[{"segmentOrder":1,"sportType":schema["sportType"],"workoutSteps":[result["step"]]}]}
    validate("create_workout",{"workout_json":payload})
    result["step"]["endConditionValue"]=1.5
    with pytest.raises(ValueError):validate("create_workout",{"workout_json":payload})


@pytest.mark.parametrize("reps,step_order,weight",[(True,1,None),(1,False,None),(0,1,None),(1,101,None),(1,1,float('nan'))])
def test_builder_rejects_invalid_values(reps,step_order,weight):
    with pytest.raises(ValueError):strength_step("SQUAT","SQUAT",reps,step_order,weight)


def test_discovery_and_builder_are_available_through_mcp_without_authentication():
    server=create_server()
    async def run():
        for name,args in [("find_garmin_exercises",{"term":"standing calf raise"}),
            ("get_garmin_workout_schema",{"sport":"strength_training"}),
            ("build_garmin_strength_step",{"category":"SQUAT","exercise":"LEG_PRESS","reps":10,"step_order":1})]:
            result=await server.call_tool(name,args)
            body=json.loads(result[0].text)
            assert "error" not in body
        tools=await server.list_tools()
        assert all(v.annotations.readOnlyHint for v in tools if v.name in {
            "find_garmin_exercises","get_garmin_workout_schema","build_garmin_strength_step"})
    asyncio.run(run())
