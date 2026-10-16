from copy import deepcopy

import pytest

from garmin_connect_mcp.strength_coaching import assess_strength

AT = "2026-10-16T12:00:00-07:00"
PLAN = [{"exercise_id":"bench", "equipment":"barbell", "regions":["chest","triceps"],
         "planned_sets":3,"planned_reps":8,"external_load_kg":60},
        {"exercise_id":"pressdown", "equipment":"cable", "regions":["triceps"],
         "planned_sets":2,"planned_reps":12}]
SET = {"set_id":"one", "performed_at":"2026-10-15T12:00:00-07:00", "exercise_id":"bench",
       "equipment":"barbell", "regions":["chest","triceps"], "reps":8, "external_load_kg":60,"rir":1}


def test_region_overlap_counts_sets_once_and_keeps_sequence():
    result = assess_strength(AT, [SET], PLAN, [{"region":"triceps","soreness":4,"pain":True}])
    first, second = result["exercises"]
    assert first["overlapping_work_sets_by_lookback_hours"]["24"] == 1
    assert first["exact_exercise_equipment_history"]["external_load_volume_kg_reps"] == 480
    assert second["exact_exercise_equipment_history"]["external_load_volume_kg_reps"] is None
    assert second["earlier_planned_exercises_with_region_overlap"] == [1]
    assert second["status"] == "review_reported_pain"
    assert first["hours_since_latest_overlapping_work_set"] == 24
    assert first["recent_72h_sets_at_0_to_2_rir"] == 1


def test_unknown_weights_and_effort_not_zero_and_warmups_excluded():
    row = {**SET,"external_load_kg":None,"rir":None}
    warmup = {**SET,"set_id":"warm","warmup":True}
    result = assess_strength(AT, [row,warmup], PLAN, [])
    first = result["exercises"][0]
    assert first["exact_exercise_equipment_history"]["external_load_volume_kg_reps"] is None
    assert first["recent_72h_sets_with_reported_rir"] == 0
    assert result["excluded_warmup_sets"] == 1


@pytest.mark.parametrize("change", [
    {"performed_at":"2026-10-17T12:00:00-07:00"},
    {"performed_at":"2026-10-15T12:00:00"}, {"reps":True},
    {"external_load_kg":float("nan")}, {"regions":["chest","chest"]},
    {"garmin_raw_weight":1000},
])
def test_bad_evidence_fails_before_analysis(change):
    with pytest.raises(ValueError):
        assess_strength(AT, [{**SET,**change}], PLAN, [])


def test_equipment_mismatch_and_duplicate_ids():
    row = {**SET,"equipment":"machine"}
    result = assess_strength(AT,[row],PLAN,[])
    assert result["exercises"][0]["exact_exercise_equipment_history"]["work_sets"] == 0
    with pytest.raises(ValueError):
        assess_strength(AT,[SET,deepcopy(SET)],PLAN,[])


def test_equivalent_timezone_instants_do_not_change_lookback():
    row = {**SET,"performed_at":"2026-10-15T19:00:00+00:00"}
    result = assess_strength(AT,[row],PLAN,[])
    assert result["exercises"][0]["hours_since_latest_overlapping_work_set"] == 24


def test_strength_mcp_accepts_typed_nested_records():
    import asyncio
    import json
    from garmin_connect_mcp.server import create_server
    result = asyncio.run(create_server().call_tool("assess_garmin_strength_session",{
        "as_of":AT,"recent_sets":[SET],"planned_exercises":PLAN,"regional_check_in":[]}))
    assert json.loads(result[0].text)["exercises"][0]["exact_exercise_equipment_history"]["reps"] == 8
