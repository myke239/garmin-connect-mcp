"""Explicit live synthetic builder audit. Never touch pre-existing templates."""
import argparse
import json
import math
import uuid
from pathlib import Path
from datetime import date, timedelta
from garmin_connect_mcp.auth import TokenStore, restore_session
from garmin_connect_mcp.runtime import session_lock, error_code
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.recovery import read_recovery, METHODS
from garmin_connect_mcp.builders import strength_workout, running_workout, swim_workout
from garmin_connect_mcp.writes import WriteService, invoke_write

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--cleanup", action="store_true")
    parser.add_argument("--new-run", action="store_true")
    args = parser.parse_args()
    if not args.run and not args.cleanup:
        parser.error("Use --run only with account-testing authorization, or --cleanup")
    audit = TokenStore(ROOT / "work/builder-audit")
    state = json.loads(audit.load()) if audit.exists() else {"run": uuid.uuid4().hex, "created": [], "checks": {}}
    if args.new_run:
        if any(not item.get("deleted") for item in state["created"]) or any("outcome" in item for item in state["checks"].values() if isinstance(item,dict)):
            raise SystemExit("Unresolved audit state must be inspected; new mutations are blocked.")
        TokenStore(ROOT / "work/builder-audit-history" / state["run"]).save(json.dumps(state))
        state = {"run":uuid.uuid4().hex,"created":[],"checks":{}}
    prefix = "MCP BUILDER AUDIT " + state["run"][:12]
    account = TokenStore()
    writes = WriteService()
    def save():
        audit.save(json.dumps(state))
    def call(method, *values, mutation=False):
        with session_lock(account):
            client = restore_session(account)
            try:
                return invoke_write(client, method, *values) if mutation else getattr(client, method)(*values)
            finally:
                account.save(client.client.dumps())
    def cleanup():
        for item in state["created"]:
            if item.get("deleted"):
                continue
            original = call("get_workout_by_id", item["id"])
            if original.get("workoutName") != item["name"]:
                raise RuntimeError("Cleanup target name mismatch")
            call("delete_workout", item["id"], mutation=True)
            try:
                call("get_workout_by_id", item["id"])
            except Exception as error:
                if error_code(error) != "NOT_FOUND":
                    raise
                item["deleted"] = True
                save()
            else:
                raise RuntimeError("Cleanup deletion not verified")
    if args.cleanup:
        cleanup()
        print("Synthetic cleanup verified.")
        return
    if state["checks"]:
        raise SystemExit("Existing audit retained; inspect it, do not rerun mutations.")
    save()
    try:
        backend = GarminService()
        day = (date.today() - timedelta(days=1)).isoformat()
        for kind in METHODS:
            response = read_recovery(backend, kind, day)
            state["checks"]["read_" + kind] = {"available": response["available"]}
            save()
        print("Recovery/performance reads passed (missing metrics remain unavailable).", flush=True)
        fixtures = [
            strength_workout(prefix + " strength", [{"category":"SQUAT","exercise":"SQUAT",
                "sets":2,"duration_seconds":20,"weight_kg":5,"rest_seconds":15}]),
            running_workout(prefix + " running", [{"distance_m":1000,"repeats":2,
                "recovery_seconds":60,"pace_s_km":[300,360]}, {"duration_seconds":60,"hr_zone":2}], 60, 60),
            swim_workout(prefix + " swimming",25,
                [{"distance_m":100,"stroke":stroke,"pace_s_100m":[90,120]} for stroke in ("any_stroke","backstroke","breaststroke","fly","free")]
                + [{"distance_m":100,"stroke":"free","equipment":equipment} for equipment in ("fins","kickboard","paddles","pull_buoy","snorkel")]
                + [{"distance_m":100,"stroke":"free","drill":drill} for drill in ("kick","pull","drill")])]
        fields = ("type","stepOrder","category","exerciseName","weightValue","endConditionValue",
            "zoneNumber","targetValueOne","targetValueTwo")
        enum_fields = {"stepType":("stepTypeId","stepTypeKey"),"endCondition":("conditionTypeId","conditionTypeKey"),
            "targetType":("workoutTargetTypeId","workoutTargetTypeKey"),"strokeType":("strokeTypeId","strokeTypeKey"),
            "equipmentType":("equipmentTypeId","equipmentTypeKey"),"drillType":("drillTypeId","drillTypeKey")}
        for index, fixture in enumerate(fixtures):
            payload = fixture["workout_json"]
            draft = writes.prepare("create_workout", {"workout_json":payload}, state["run"] + "-" + str(index))
            state["checks"]["draft_" + str(index)] = {"draft_id": draft["draft_id"]}
            save()
            result = writes.commit(draft["draft_id"])
            if result["status"] != "completed":
                state["checks"]["draft_" + str(index)]["outcome"] = result
                save()
                raise RuntimeError("Uncertain write; stop and inspect retained audit/journal")
            identity = result["result"]["workoutId"][0]
            state["created"].append({"id":identity,"name":payload["workoutName"]})
            save()
            stored = call("get_workout_by_id",identity)
            state["checks"]["stored_" + str(index)] = stored
            save()
            expected = payload["workoutSegments"][0]["workoutSteps"]
            actual = stored["workoutSegments"][0]["workoutSteps"]
            assert len(expected) == len(actual), "step count changed"
            for wanted, got in zip(expected,actual):
                for field in fields:
                    if field in wanted:
                        actual_value = got.get(field)
                        if isinstance(wanted[field], (int,float)) and isinstance(actual_value, (int,float)):
                            assert math.isclose(wanted[field],actual_value,rel_tol=1e-5,abs_tol=1e-5), "readback mismatch: " + field
                        else:
                            assert wanted[field] == actual_value, "readback mismatch: " + field
                for field, keys in enum_fields.items():
                    if field in wanted:
                        assert all(wanted[field].get(key) == (got.get(field) or {}).get(key) for key in keys), "readback mismatch: " + field
            if "poolLength" in payload:
                assert stored.get("poolLength") == payload["poolLength"], "pool metadata changed"
            state["checks"]["readback_" + str(index)] = True
            save()
            print("Builder " + str(index) + " create/readback passed.",flush=True)
    finally:
        cleanup()
    print("Builder audit passed; all known synthetic templates removed.")


if __name__ == "__main__":
    main()
