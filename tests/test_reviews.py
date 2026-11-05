"""Synthetic review behavior, independent schedule oracles, and durable failure paths."""
import asyncio
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta

import pytest
from pydantic import ValidationError

from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.review_analysis import analyze_logs
from garmin_connect_mcp.review_models import LogReview, ReviewSchedule, timestamp
from garmin_connect_mcp.review_monitor import check
from garmin_connect_mcp.review_schedule import build_schedule, occurrence, run_id
from garmin_connect_mcp.review_state import ReviewStore, RunReport
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.writes import WriteService


def evidence():
    return {"calendar_date": "2026-01-01", "timezone": "America/Los_Angeles", "as_of": "2026-01-02T08:00:00-08:00",
            "coverage": [{"source": name, "status": "available", "fetched_at": "2026-01-02T07:59:00-08:00"}
                         for name in ("nutrition", "strength", "lifestyle")],
            "diary": {"complete": True, "calories_kcal": 1000, "goal_kcal": 2000},
            "routines": [{"routine_id": "habit", "label": "Synthetic routine", "confirmed": True,
                          "expected_amount": 10, "unit": "g", "recorded": "missing"}]}


def spec(**changes):
    return {"schedule_id": "morning", "template": "daily_logs", "timezone": "America/Los_Angeles",
            "local_time": "08:00", "start_date": "2026-01-01", "sources": ["nutrition"], **changes}


def test_low_log_is_a_question_zero_distinct_from_unknown_and_skipped():
    row = evidence()
    findings = analyze_logs(row)["findings"]
    assert {f["rule"] for f in findings} == {"low_logged_calories", "routine_unconfirmed"}
    assert "1000 kcal" in findings[0]["evidence"]
    row["diary"]["calories_kcal"] = None
    row["routines"][0]["recorded"] = "skipped"
    assert analyze_logs(row)["findings"] == []
    row["diary"]["calories_kcal"] = 0
    assert analyze_logs(row)["findings"][0]["rule"] == "low_logged_calories"
    row["routines"][0].update(confirmed=False, recorded="missing")
    assert len(analyze_logs(row)["findings"]) == 1


def test_only_verified_comparable_work_sets_flag_isolated_outlier():
    row = evidence()
    row["sets"] = [{"activity_id": "activity", "set_id": str(i), "exercise_id": "PRESS",
                    "equipment": "barbell", "reps": 8, "load": value, "load_unit": "kg", "kind": "work",
                    "comparison_group": "total-barbell"} for i, value in enumerate([60, 60, 600])]
    result = analyze_logs(row)
    outliers = [f for f in result["findings"] if f["rule"] == "isolated_load_deviation"]
    assert len(outliers) == 1 and "600 kg" in outliers[0]["evidence"]
    row["sets"][-1]["kind"] = "warmup"
    assert not any(f["rule"] == "isolated_load_deviation" for f in analyze_logs(row)["findings"])
    for item in row["sets"]:
        item.update(kind="work", load_unit="garmin_raw_unverified")
    rules = [f["rule"] for f in analyze_logs(row)["findings"]]
    assert rules.count("unverified_load_units") == 1 and "isolated_load_deviation" not in rules
    row["sets"][0]["exercise_id"] = None
    assert any(f["rule"] == "unknown_exercise" for f in analyze_logs(row)["findings"])


@pytest.mark.parametrize("change", [{"intentional_variation": True}, {"comparison_group": None},
                                  {"equipment": "machine"}, {"reps": 3}, {"kind": "drop"}])
def test_legitimate_variations_not_corrected(change):
    row = evidence()
    row["sets"] = [{"activity_id": "a", "set_id": str(i), "exercise_id": "press", "equipment": "barbell",
                    "reps": 8, "load": load, "load_unit": "kg", "kind": "work", "comparison_group": "a"}
                   for i, load in enumerate([60, 60, 100])]
    row["sets"][-1].update(change)
    assert not any(f["rule"] == "isolated_load_deviation" for f in analyze_logs(row)["findings"])


def test_ids_stable_under_reordering_and_coverage_never_silent():
    row = evidence()
    first = analyze_logs(row)
    row["coverage"].reverse()
    assert analyze_logs(row)["findings"] == first["findings"]
    row["coverage"][0] = {"source": "lifestyle", "status": "unavailable", "reason": "AUTH_REQUIRED"}
    row["routines"] = []
    assert analyze_logs(row)["status"] == "partial"
    row = {k: v for k, v in evidence().items() if k not in {"diary", "routines"}}
    row["coverage"] = [{"source": "nutrition", "status": "unavailable", "reason": "AUTH_REQUIRED"}]
    result = analyze_logs(row)
    assert result["status"] == "failed" and result["summary"] and result["coverage"][0]["reason"] == "AUTH_REQUIRED"


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(calendar_date="2026-01-02"),
    lambda r: r.update(as_of="2026-01-02T08:00:00"),
    lambda r: r["diary"].update(calories_kcal=True),
    lambda r: r["diary"].update(calories_kcal=float("nan")),
    lambda r: r["diary"].update(username="unwanted"),
    lambda r: r["routines"][0].update(unit=None),
    lambda r: r["coverage"][0].update(fetched_at="2027-01-01T00:00:00Z"),
    lambda r: r["coverage"].append(r["coverage"][0]),
])
def test_review_rejects_ambiguous_or_invalid_inputs(mutation):
    row = evidence()
    mutation(row)
    with pytest.raises((ValueError, ValidationError)):
        LogReview.model_validate(row)


def test_dst_gap_fold_and_calendar_interval_independent_expected_utc():
    spring = spec(local_time="02:30", start_date="2026-03-01")
    assert occurrence(spring, date(2026, 3, 8)) == datetime(2026, 3, 8, 10, tzinfo=UTC)
    fall = spec(local_time="01:30", start_date="2026-11-01")
    assert occurrence(fall, date(2026, 11, 1)) == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)
    interval = spec(interval=2, start_date="2026-03-07")
    assert occurrence(interval, date(2026, 3, 8)) is None
    assert occurrence(interval, date(2026, 3, 9)) == datetime(2026, 3, 9, 15, tzinfo=UTC)
    weekly = spec(frequency="weekly", weekdays=[0, 4], interval=2, start_date="2026-01-01")
    assert occurrence(weekly, date(2026, 1, 2)) is not None
    assert occurrence(weekly, date(2026, 1, 5)) is None
    assert occurrence(weekly, date(2026, 1, 12)) is not None


def test_builder_is_only_a_template_and_uses_real_civil_times():
    result = build_schedule(spec(), "2026-01-01T07:00:00-08:00")
    assert result["next_runs"][0]["due_at"] == "2026-01-01T16:00:00+00:00"
    assert result["host_schedule_created"] is False and result["monitor_installed"] is False
    assert len(result["next_runs"]) == 3
    assert build_schedule(spec(enabled=False), "2026-01-01T07:00:00-08:00")["next_runs"] == []
    with pytest.raises(ValidationError):
        ReviewSchedule.model_validate(spec(frequency="weekly"))


@pytest.fixture
def ledger(tmp_path):
    clock = [timestamp("2026-01-01T07:00:00-08:00")]
    store = ReviewStore(tmp_path, clock=lambda: clock[0])
    store.update({"operation": "configure", "schedule": spec(), "host_task_id": "host-1"}, 0)
    return store, clock


def start(store, clock):
    clock[0] = timestamp("2026-01-01T08:00:00-08:00")
    return store.update({"operation": "start", "schedule_id": "morning", "due_at": clock[0].isoformat()},
                        store.read()["revision"])


def report(status="completed", findings=None):
    return {"status": status, "summary": "Synthetic review result.", "findings": findings or [],
            "coverage": [{"source": "nutrition", "status": "available", "fetched_at": "2026-01-01T08:00:00-08:00"}],
            "errors": ["Synthetic timeout."] if status == "failed" else []}


def finish(store, claim, payload=None):
    return store.update({"operation": "finish", "run_id": claim["run_id"], "claim_token": claim["claim_token"],
                         "report": payload or report()}, store.read()["revision"])


def test_missed_run_without_agent_start_is_detected(ledger):
    store, clock = ledger
    clock[0] = timestamp("2026-01-01T08:16:00-08:00")
    health, code = check(store)
    assert code == 1 and health["alerts"][0]["code"] == "MISSED_RUN"
    assert store.read()["run_count"] == 0  # Monitoring itself does not claim work.


def test_claim_persistence_duplicate_prevention_and_delivery_failure(ledger):
    store, clock = ledger
    claim = start(store, clock)
    assert claim["claimed"]
    restarted = ReviewStore(store.directory, clock=lambda: clock[0])
    duplicate = start(restarted, clock)
    assert duplicate["claimed"] is False and "claim_token" not in duplicate
    assert "claim_token" not in restarted.read("runs")["items"][0]
    finish(restarted, claim)
    clock[0] += timedelta(minutes=16)
    assert check(restarted)[0]["alerts"][0]["code"] == "DELIVERY_UNCONFIRMED"
    restarted.update({"operation": "delivery", "run_id": claim["run_id"], "status": "failed", "receipt": "synthetic transport error"}, restarted.read()["revision"])
    assert check(restarted)[0]["alerts"][0]["code"] == "DELIVERY_FAILED"
    restarted.update({"operation": "delivery", "run_id": claim["run_id"], "status": "accepted", "receipt": "synthetic actual receipt"}, restarted.read()["revision"])
    assert check(restarted)[1] == 0


def test_expired_run_cannot_report_success_and_wrong_claim_cannot_finish(ledger):
    store, clock = ledger
    claim = start(store, clock)
    bad = {**claim, "claim_token": "wrong"}
    with pytest.raises(RequestError, match="REVIEW_CLAIM_REQUIRED"):
        finish(store, bad)
    clock[0] += timedelta(minutes=16)
    assert check(store)[0]["alerts"][0]["code"] == "RUN_DEADLINE_EXCEEDED"
    with pytest.raises(ValueError, match="Expired"):
        finish(store, claim)
    finish(store, claim, report("failed"))
    assert store.read("runs")["items"][0]["report"]["errors"]


def test_two_workers_only_one_commits_claim_and_revision_conflict_preserves_data(ledger):
    store, clock = ledger
    clock[0] = timestamp("2026-01-01T08:00:00-08:00")
    command = {"operation": "start", "schedule_id": "morning", "due_at": clock[0].isoformat()}
    def claim():
        try:
            return store.update(command, 1)["claimed"]
        except RequestError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: claim(), range(2)))
    assert sorted(str(v) for v in results) == ["REVIEW_STATE_CONFLICT", "True"]
    assert store.read()["run_count"] == 1


def test_schedule_edits_do_not_erase_old_missed_occurrences_or_paused_reports(ledger):
    store, clock = ledger
    clock[0] = timestamp("2026-01-01T08:20:00-08:00")
    store.update({"operation": "configure", "schedule": spec(local_time="09:00"), "host_task_id": "host-1"}, 1)
    assert check(store)[0]["alerts"][0]["code"] == "MISSED_RUN"
    store.update({"operation": "configure", "schedule": spec(enabled=False), "host_task_id": "host-1"}, 2)
    assert check(store)[0]["alerts"][0]["code"] == "MISSED_RUN"


def test_resolutions_persist_identical_evidence_and_reopen_changed_evidence(ledger):
    store, clock = ledger
    claim = start(store, clock)
    finding = analyze_logs(evidence())["findings"][0]
    finish(store, claim, report(findings=[finding]))
    store.update({"operation": "resolve", "finding_id": finding["finding_id"], "resolution": "correct_as_recorded",
                  "answer": "Confirmed synthetic record."}, store.read()["revision"])
    clock[0] += timedelta(days=1)
    next_claim = store.update({"operation": "start", "schedule_id": "morning", "due_at": clock[0].isoformat()}, store.read()["revision"])
    finish(store, next_claim, report(findings=[finding]))
    assert store.read("findings")["items"][0]["resolution"] == "correct_as_recorded"
    clock[0] += timedelta(days=1)
    third = store.update({"operation": "start", "schedule_id": "morning", "due_at": clock[0].isoformat()}, store.read()["revision"])
    finding["evidence"] = "Source value changed."
    finish(store, third, report(findings=[finding]))
    saved = store.read("findings")["items"][0]
    assert saved["resolution"] is None and saved["previous_resolution"] == "correct_as_recorded"


def test_coverage_contract_rejects_false_success_and_accepts_total_failure(ledger):
    for invalid in [{"status": "completed", "summary": "No data"}, {"status": "failed", "summary": "No reason"},
                    {**report(), "coverage": [{"source": "nutrition", "status": "unavailable", "reason": "TIMEOUT"}]}]:
        with pytest.raises(ValidationError):
            RunReport.model_validate(invalid)
    store, clock = ledger
    claim = start(store, clock)
    missing = report()
    missing["coverage"][0]["source"] = "plan"
    with pytest.raises(ValueError, match="configured source"):
        finish(store, claim, missing)
    finish(store, claim, {"status": "failed", "summary": "Could not connect.", "errors": ["AUTH_REQUIRED: reconnect provider."]})
    assert store.read("runs")["items"][0]["status"] == "failed"


def test_local_policy_global_revocation_and_corrupt_storage_are_explicit(ledger):
    store, clock = ledger
    store.settings.save(json.dumps({"enabled": True, "operations": ["start"]}))
    with pytest.raises(RequestError, match="REVIEW_OPERATION_DENIED"):
        store.update({"operation": "profile", "profile": {}}, 1)
    WriteService(store.directory).settings.save('{"enabled":false}')
    with pytest.raises(RequestError, match="WRITES_DISABLED"):
        start(store, clock)
    store.store.path.write_bytes(b"corrupted synthetic store")
    health, code = check(store)
    assert code == 2 and health["alerts"][0]["code"] == "REVIEW_MONITOR_FAILED"


def test_monitor_cli_nonzero_json_without_health_content(tmp_path):
    env = {**os.environ, "GARMIN_MCP_DATA_DIR": str(tmp_path)}
    result = subprocess.run([sys.executable, "-m", "garmin_connect_mcp.review_monitor", "--once"],
                            env=env, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 1
    value = json.loads(result.stdout)
    assert value["alerts"][0]["code"] == "NO_REVIEW_SCHEDULES" and not result.stderr


def test_mcp_examples_scope_annotations_and_profile_removal(tmp_path):
    async def exercise():
        backend = GarminService(TokenStore(tmp_path), runner=lambda *a: pytest.fail("Unexpected account call"))
        server = create_server(backend)
        guide = json.loads((await server.call_tool("get_garmin_review_guide", {}))[0].text)
        for example in guide["examples"]:
            result = json.loads((await server.call_tool(example["tool"], example["arguments"]))[0].text)
            assert "error" not in result
        inputs = {"command": {"operation": "profile", "profile": {}}, "expected_revision": 0}
        remote = create_server(backend, remote_access=True)
        denied = json.loads((await remote.call_tool("update_garmin_review_state", inputs))[0].text)
        assert denied["error"]["code"] == "WRITE_SCOPE_REQUIRED"
        assert not ReviewStore(tmp_path).store.exists()
        accepted = json.loads((await server.call_tool("update_garmin_review_state", inputs))[0].text)
        assert accepted["revision"] == 1
        tools = {t.name: t for t in await server.list_tools()}
        assert tools["update_garmin_review_state"].annotations.readOnlyHint is False
        readonly = create_server(backend, tool_profile="read-only")
        assert "update_garmin_review_state" not in {t.name for t in await readonly.list_tools()}
    asyncio.run(exercise())


def test_routine_weekdays_and_meal_ids_survive_reordering():
    row = evidence()  # Thursday
    row["routines"][0]["weekdays"] = [0, 2, 4]
    row["diary"]["missing_expected_meals"] = ["breakfast", "dinner"]
    first = analyze_logs(row)["findings"]
    assert not any(f["rule"] == "routine_unconfirmed" for f in first)
    row["diary"]["missing_expected_meals"].reverse()
    assert analyze_logs(row)["findings"] == first


def test_expired_worker_recovery_fences_late_results(ledger):
    store, clock = ledger
    claim = start(store, clock)
    with pytest.raises(ValueError):
        store.update({"operation": "recover", "run_id": claim["run_id"]}, store.read()["revision"])
    clock[0] += timedelta(minutes=16)
    store.update({"operation": "recover", "run_id": claim["run_id"]}, store.read()["revision"])
    assert store.read("runs")["items"][0]["report"]["status"] == "failed"
    with pytest.raises(RequestError, match="REVIEW_STATE_CONFLICT"):
        finish(store, claim)


def test_missed_occurrence_remains_after_lookback_and_history_gap_needs_ack(ledger):
    store, clock = ledger
    clock[0] = timestamp("2026-01-01T08:20:00-08:00")
    store.update({"operation": "profile", "profile": {}}, 1)
    missed_id = run_id("morning", timestamp("2026-01-01T08:00:00-08:00"))
    assert store.read("runs")["items"][0]["status"] == "missed"
    clock[0] += timedelta(days=40)
    assert any(a["code"] == "HISTORY_WINDOW_EXCEEDED" for a in check(store)[0]["alerts"])
    store.update({"operation": "profile", "profile": {}}, store.read()["revision"])
    alerts = check(store)[0]["alerts"]
    assert any(a.get("run_id") == missed_id for a in alerts)
    assert any(a["code"] == "HISTORY_WINDOW_EXCEEDED" for a in alerts)
    store.update({"operation": "acknowledge_gap", "acknowledgement": "Reviewed unobserved period with the user."}, store.read()["revision"])
    assert not any(a["code"] == "HISTORY_WINDOW_EXCEEDED" for a in check(store)[0]["alerts"])
    assert any(a.get("run_id") == missed_id for a in check(store)[0]["alerts"])


def test_atomic_storage_failure_keeps_original_and_is_reported(ledger, monkeypatch):
    store, clock = ledger
    original = store.store.path.read_bytes()
    monkeypatch.setattr(store.store, "save", lambda value: (_ for _ in ()).throw(OSError("synthetic storage failure")))
    with pytest.raises(OSError):
        start(store, clock)
    assert store.store.path.read_bytes() == original
    assert store.read()["revision"] == 1


def test_capacity_failure_does_not_drop_existing_state(ledger, monkeypatch):
    import garmin_connect_mcp.review_state as module
    store, _ = ledger
    before = store.store.path.read_bytes()
    monkeypatch.setattr(module, "MAX_BYTES", 2000)
    with pytest.raises(RequestError, match="REVIEW_STORAGE_FULL"):
        store.update({"operation": "profile", "profile": {"preferences": ["x" * 500] * 10}}, 1)
    assert before == store.store.path.read_bytes()


def test_read_pagination_and_no_secrets_in_monitor(ledger):
    store, clock = ledger
    for day in range(1, 8):
        clock[0] = timestamp(f"2026-01-{day:02}T08:00:00-08:00")
        claim = store.update({"operation": "start", "schedule_id": "morning", "due_at": clock[0].isoformat()}, store.read()["revision"])
        finish(store, claim)
    first = store.read("runs", 0, 50)
    assert len(first["items"]) == 5 and first["next_start"] == 5 and first["total"] == 7
    second = store.read("runs", first["next_start"], 50)
    assert len(second["items"]) == 2 and second["next_start"] is None
    assert "claim_token" not in json.dumps(first)
    assert "Synthetic review result" not in json.dumps(check(store)[0])


def test_future_fetch_claim_and_finish_validation_and_window(ledger):
    store, clock = ledger
    with pytest.raises(ValueError):
        store.update({"operation": "start", "schedule_id": "morning", "due_at": "2026-01-02T08:00:00-08:00"}, 1)
    claim = start(store, clock)
    assert claim["review_window"] == {"start_date": "2025-12-31", "end_date": "2025-12-31", "timezone": "America/Los_Angeles"}
    payload = report()
    payload["coverage"][0]["fetched_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="future"):
        finish(store, claim, payload)


def test_delete_requires_literal_confirmation_and_preserves_external_boundary(ledger):
    store, _ = ledger
    for confirmation in (False, "true", 1):
        with pytest.raises(ValidationError):
            store.update({"operation": "delete", "confirm_delete": confirmation}, 1)
    result = store.update({"operation": "delete", "confirm_delete": True}, 1)
    assert result["deleted"] and result["host_tasks_cancelled"] is False
    assert store.read()["schedules"] == []


def test_owner_review_policy_command_can_deny_all_without_disabling_reads(tmp_path):
    env = {**os.environ, "GARMIN_MCP_DATA_DIR": str(tmp_path)}
    result = subprocess.run([sys.executable, "-m", "garmin_connect_mcp.manage", "reviews-enable", "--operations"],
                            env=env, capture_output=True, text=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["review_policy"]["operations"] == []
    store = ReviewStore(tmp_path)
    assert store.read()["revision"] == 0
    with pytest.raises(RequestError, match="REVIEW_OPERATION_DENIED"):
        store.update({"operation": "profile", "profile": {}}, 0)
