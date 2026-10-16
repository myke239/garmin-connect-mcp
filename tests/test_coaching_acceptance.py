"""Independent numerical oracles and executable discovery examples, never live accounts."""
import asyncio
from copy import deepcopy
from datetime import date, timedelta
import json

import pytest

from garmin_connect_mcp.coaching import analyze_day, compare_outcomes, lifestyle_association
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.strength_coaching import assess_strength


def day(index, value):
    return {"calendar_date":(date(2026,1,31)-timedelta(days=index)).isoformat(),
            "timezone":"America/Los_Angeles","fetched_at":"2026-01-31T12:00:00-08:00",
            "metrics":{"resting_hr_bpm":{"value":value,"unit":"bpm","source":"user","source_field":"test"}}}


def test_nonconstant_baseline_independent_percentile_oracle_and_input_permutation():
    rows = [day(0,100)] + [day(index,40+index) for index in range(1,21)]
    result = analyze_day("2026-01-31","America/Los_Angeles",rows,[],{},[])["metrics"]["resting_hr_bpm"]
    assert result["median"] == 50.5
    assert result["p10"] == pytest.approx(42.9)
    assert result["p90"] == pytest.approx(58.1)
    reverse = analyze_day("2026-01-31","America/Los_Angeles",list(reversed(rows)),[],{},[])
    assert reverse["metrics"]["resting_hr_bpm"] == result
    assert result["baseline_observations"] == 20
    assert result["deviation_from_median"] == 49.5


def test_lifestyle_lag_direction_and_unknowns_against_hand_computed_groups():
    # Jan 10..23 exposures align to Jan 11..24 outcomes; alternating values give 5 bpm difference.
    rows = []
    events = []
    for index in range(14):
        exposure_date = date(2026,1,10)+timedelta(days=index)
        row = day(0,55 if index % 2 else 50)
        row["calendar_date"] = (exposure_date+timedelta(days=1)).isoformat()
        rows.append(row)
        events.append({"calendar_date":exposure_date.isoformat(),"amount":1 if index % 2 else 0})
    result = lifestyle_association("2026-01-31",rows,events,"resting_hr_bpm",1)
    assert result["exposed_days"] == result["recorded_zero_days"] == 7
    assert result["difference_in_medians"] == 5
    events[0]["amount"] = None
    result = lifestyle_association("2026-01-31",rows,events,"resting_hr_bpm",1)
    assert result["status"] == "insufficient_data" and result["excluded_days"] == 1


def test_strength_window_boundaries_and_no_cross_equipment_volume():
    exercise = {"exercise_id":"press","equipment":"barbell","regions":["chest"]}
    sets = [{**exercise,"set_id":str(hours),"performed_at":f"2026-01-{31-hours//24:02}T12:00:00-08:00",
             "reps":10,"external_load_kg":20,"rir":0} for hours in (24,48,72,96)]
    sets.append({**sets[0],"set_id":"different","equipment":"machine","external_load_kg":100})
    result = assess_strength("2026-01-31T12:00:00-08:00",sets,
                             [{**exercise,"planned_sets":3,"planned_reps":10}],[])["exercises"][0]
    assert result["overlapping_work_sets_by_lookback_hours"] == {"24":2,"48":3,"72":4}
    assert result["exact_exercise_equipment_history"]["external_load_volume_kg_reps"] == 800
    assert result["recent_72h_sets_at_0_to_2_rir"] == 4


def test_outcome_percentiles_and_unknown_session_abstention():
    rows = [{"calendar_date":f"2026-01-0{i+1}","session_type":"fixed","metric":"reps",
             "value":8+i,"completed":True} for i in range(5)]
    result = compare_outcomes("2026-01-10","fixed","reps",rows)
    assert (result["median"],result["p10"],result["p90"]) == (10,8.4,11.6)
    assert compare_outcomes("2026-01-10","unmatched","reps",rows)["status"] == "insufficient_data"


def test_discovered_guide_examples_execute_without_account_access():
    async def exercise_examples():
        server = create_server(tool_profile="recovery")
        response = await server.call_tool("get_garmin_coaching_guide",{})
        guide = json.loads(response[0].text)
        assert len(guide["input_schemas"]) == 5
        results = {}
        for example in guide["examples"]:
            result = await server.call_tool(example["tool"],example["arguments"])
            payload = json.loads(result[0].text)
            assert "error" not in payload
            results[example["tool"]] = payload
        assert results["compare_garmin_workout_outcomes"]["median"] == 10
        assert results["assess_garmin_strength_session"]["exercises"][1]["earlier_planned_exercises_with_region_overlap"] == [1]
        assert results["analyze_garmin_daily_recovery"]["nutrition"][0]["goal_difference"]["calories"] == -400
        assert results["analyze_garmin_lifestyle_association"]["status"] == "insufficient_data"
    asyncio.run(exercise_examples())


def test_transport_rejects_unknown_fields_boolean_numbers_and_bad_units():
    async def invalid_inputs():
        server = create_server()
        guide = json.loads((await server.call_tool("get_garmin_coaching_guide",{}))[0].text)
        args = guide["examples"][0]["arguments"]
        for invalid in (True,"50",float("inf")):
            candidate = deepcopy(args)
            candidate["history"][0]["metrics"]["overnight_hrv_ms"]["value"] = invalid
            with pytest.raises(Exception):
                await server.call_tool("analyze_garmin_daily_recovery",candidate)
        candidate = deepcopy(args)
        candidate["history"][0]["metrics"]["overnight_hrv_ms"]["unit"] = "seconds"
        with pytest.raises(Exception):
            await server.call_tool("analyze_garmin_daily_recovery",candidate)
        candidate = deepcopy(args)
        candidate["nutrition"][0]["username"] = "alternate-person"
        with pytest.raises(Exception):
            await server.call_tool("analyze_garmin_daily_recovery",candidate)
    asyncio.run(invalid_inputs())
