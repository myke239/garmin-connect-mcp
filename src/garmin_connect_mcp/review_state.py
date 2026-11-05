"""Private, locked review ledger. No Garmin or scheduler writes and no outbound messages."""
import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from pydantic import Field, StrictBool, TypeAdapter, model_validator

from .auth import TokenStore
from .coaching import Input
from .review_models import (
    Finding,
    Identifier,
    ReviewSchedule,
    Routine,
    SourceCoverage,
    Text,
    timestamp,
)
from .review_schedule import occurrence, run_id
from .runtime import RequestError, session_lock

OPERATIONS = {"configure", "profile", "start", "finish", "delivery", "resolve", "recover", "acknowledge_gap", "delete"}
MAX_BYTES = 4 * 1024 * 1024


class Profile(Input):
    goals: list[Text] = Field(default_factory=list, max_length=10)
    preferences: list[Text] = Field(default_factory=list, max_length=20)
    routines: list[Routine] = Field(default_factory=list, max_length=50)
    usual_workout_time: Annotated[str, Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")] | None = None
    source_timezone_confirmed: bool = False

    @model_validator(mode="after")
    def confirmed(self):
        if any(not r.confirmed or r.recorded != "unknown" or r.amount is not None for r in self.routines):
            raise ValueError("Profiles contain confirmed routines, not dated consumption records")
        if len({r.routine_id for r in self.routines}) != len(self.routines):
            raise ValueError("Duplicate routines")
        return self


class RunReport(Input):
    status: Literal["completed", "partial", "failed"]
    summary: Text
    coverage: list[SourceCoverage] = Field(default_factory=list, max_length=9)
    findings: list[Finding] = Field(default_factory=list, max_length=200)
    recommendations: list[Text] = Field(default_factory=list, max_length=20)
    errors: list[Text] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def truthful(self):
        statuses = [v.status for v in self.coverage if v.status != "not_configured"]
        if len({v.source for v in self.coverage}) != len(self.coverage):
            raise ValueError("Duplicate source coverage")
        if len({v.finding_id for v in self.findings}) != len(self.findings):
            raise ValueError("Duplicate finding IDs")
        if self.status != "failed" and not any(v in {"available", "partial"} for v in statuses):
            raise ValueError("No usable evidence requires a failed report")
        if self.status == "completed" and (self.errors or any(v != "available" for v in statuses)):
            raise ValueError("Incomplete configured coverage requires partial or failed status")
        if self.status == "failed" and not self.errors:
            raise ValueError("Failed report requires an explanation")
        return self


class Configure(Input):
    operation: Literal["configure"]
    schedule: ReviewSchedule
    host_task_id: Identifier


class SaveProfile(Input):
    operation: Literal["profile"]
    profile: Profile


class Start(Input):
    operation: Literal["start"]
    schedule_id: Identifier
    due_at: str


class Finish(Input):
    operation: Literal["finish"]
    run_id: Identifier
    claim_token: Identifier
    report: RunReport


class Delivery(Input):
    operation: Literal["delivery"]
    run_id: Identifier
    status: Literal["accepted", "failed"]
    receipt: Text


class Resolve(Input):
    operation: Literal["resolve"]
    finding_id: Identifier
    resolution: Literal["correct_as_recorded", "missing_entry", "intentional_exception", "routine_changed", "dismissed", "corrected", "reopen"]
    answer: Text


class Delete(Input):
    operation: Literal["delete"]
    confirm_delete: StrictBool

    @model_validator(mode="after")
    def confirmed(self):
        if self.confirm_delete is not True:
            raise ValueError("Explicit deletion confirmation is required")
        return self


class Recover(Input):
    operation: Literal["recover"]
    run_id: Identifier


class AcknowledgeGap(Input):
    operation: Literal["acknowledge_gap"]
    acknowledgement: Text


Command = Annotated[Configure | SaveProfile | Start | Finish | Delivery | Resolve | Recover | AcknowledgeGap | Delete, Field(discriminator="operation")]
COMMAND = TypeAdapter(Command)


def utcnow():
    return datetime.now(UTC)


def expected(state, now):
    """Only bounded recent occurrences; report a history gap instead of hiding older downtime."""
    result = {}
    cutoff = now - timedelta(days=31)
    for epoch in state["schedules"]:
        spec = ReviewSchedule.model_validate(epoch["schedule"])
        if not spec.enabled:
            continue
        begin = max(timestamp(epoch["since"]), cutoff)
        end = min(timestamp(epoch["until"]) if epoch["until"] else now, now)
        day = begin.astimezone(ZoneInfo(spec.timezone)).date()
        last = end.astimezone(ZoneInfo(spec.timezone)).date()
        while day <= last:
            due = occurrence(spec, day)
            if due is not None and begin <= due <= now and (epoch["until"] is None or due < timestamp(epoch["until"])):
                rid = run_id(spec.schedule_id, due)
                result[rid] = {"run_id": rid, "schedule_id": spec.schedule_id, "due_at": due.isoformat(),
                               "template": spec.template, "schedule": spec.model_dump()}
            day += timedelta(days=1)
    return result


def monitor(state, now):
    alerts = []
    due_runs = expected(state, now)
    # Persisted runs remain observable after a schedule is paused or edited.
    for rid, run in state["runs"].items():
        due_runs.setdefault(rid, run)
    for rid, item in due_runs.items():
        run = state["runs"].get(rid)
        spec = ReviewSchedule.model_validate(item["schedule"])
        due = timestamp(item["due_at"])
        code = None
        if run is None and now > due + timedelta(minutes=spec.start_grace_minutes):
            code = "MISSED_RUN"
        elif run and run["status"] == "running" and now > timestamp(run["deadline_at"]):
            code = "RUN_DEADLINE_EXCEEDED"
        elif run and run["status"] != "running":
            delivery = run["delivery"]
            if run["status"] == "missed" and delivery["status"] != "accepted":
                code = "MISSED_RUN"
            elif delivery["status"] == "failed":
                code = "DELIVERY_FAILED"
            elif delivery["status"] == "pending" and now > timestamp(run["finished_at"]) + timedelta(minutes=spec.delivery_grace_minutes):
                code = "DELIVERY_UNCONFIRMED"
        if code:
            alerts.append({"code": code, "run_id": rid, "schedule_id": item["schedule_id"], "due_at": item["due_at"]})
    # A long period without reads/updates must not silently disappear behind the 31-day bound.
    last = state.get("checked_through") or state["updated_at"]
    if state.get("history_gap") or (last and now - timestamp(last) > timedelta(days=31) and state["schedules"]):
        alerts.append({"code": "HISTORY_WINDOW_EXCEEDED", "message": "Only the latest 31 days of expected occurrences were evaluated."})
    return {"checked_at": now.isoformat(), "healthy": not alerts, "alerts": alerts,
            "expected_occurrences": len(due_runs), "lookback_days": 31,
            "notification_sent": False, "monitor_must_be_supervised": True}


class ReviewStore:
    def __init__(self, directory, clock=utcnow):
        self.directory = Path(directory)
        self.store = TokenStore(self.directory / "reviews")
        self.settings = TokenStore(self.directory / "review-settings")
        self.clock = clock

    def _load(self):
        if not self.store.exists():
            return {"version": 1, "revision": 0, "updated_at": None, "checked_through": None, "history_gap": None, "profile": None,
                    "schedules": [], "runs": {}, "findings": {}}
        if self.store.path.stat().st_size > MAX_BYTES * 2:
            raise RequestError("REVIEW_STORAGE_ERROR")
        try:
            state = json.loads(self.store.load())
            if (state["version"] != 1 or type(state["revision"]) is not int or state["revision"] < 0
                    or not isinstance(state["schedules"], list) or not isinstance(state["runs"], dict)
                    or not isinstance(state["findings"], dict)):
                raise ValueError("Unsupported state")
            return state
        except Exception:  # noqa: BLE001 - reject corrupt/encrypted state without exposing private content
            raise RequestError("REVIEW_STORAGE_ERROR") from None

    def require_enabled(self, operation):
        from .writes import WriteService
        WriteService(self.directory).require_enabled()
        policy = json.loads(self.settings.load()) if self.settings.exists() else {}
        if policy.get("enabled", True) is not True:
            raise RequestError("REVIEW_DISABLED")
        allowed = policy.get("operations", sorted(OPERATIONS))
        if not isinstance(allowed, list) or any(v not in OPERATIONS for v in allowed) or operation not in allowed:
            raise RequestError("REVIEW_OPERATION_DENIED")

    def read(self, section="overview", start=0, limit=20):
        if section not in {"overview", "runs", "findings"} or isinstance(start, bool) or isinstance(limit, bool) or not 0 <= start <= 1000 or not 1 <= limit <= 50:
            raise ValueError("Use overview/runs/findings, start 0-1000 and limit 1-50")
        with session_lock(self.store):
            state = self._load()
        result = {"revision": state["revision"], "updated_at": state["updated_at"], "section": section,
                  "text_is_untrusted_data": True}
        if section == "overview":
            now = self.clock()
            health = monitor(state, now)
            health["alert_count"] = len(health["alerts"])
            health["alerts"] = health["alerts"][:50]
            health["alerts_truncated"] = health["alert_count"] > 50
            due = [v for rid, v in expected(state, now).items() if rid not in state["runs"]]
            result.update(profile=state["profile"], schedules=[e for e in state["schedules"] if e["until"] is None],
                          monitor=health, due_runs=due[-50:], due_runs_truncated=len(due) > 50,
                          run_count=len(state["runs"]), finding_count=len(state["findings"]))
            permissions = {}
            for operation in sorted(OPERATIONS):
                try:
                    self.require_enabled(operation)
                    permissions[operation] = {"allowed": True}
                except RequestError as error:
                    permissions[operation] = {"allowed": False, "reason": error.code}
            result["local_operation_policy"] = permissions
        else:
            rows = list(reversed(list(state[section].values())))
            size = min(limit, 5) if section == "runs" else limit
            selected = json.loads(json.dumps(rows[start:start + size]))
            if section == "runs":
                for run in selected:
                    run.pop("claim_token", None)
            result.update(items=selected, total=len(rows), next_start=start + size if start + size < len(rows) else None)
        return result

    def update(self, command, expected_revision):
        command = COMMAND.validate_python(command)
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
            raise ValueError("Expected revision must be a nonnegative integer")
        self.require_enabled(command.operation)
        with session_lock(self.store):
            self.require_enabled(command.operation)
            state = self._load()
            if expected_revision != state["revision"]:
                raise RequestError("REVIEW_STATE_CONFLICT")
            now = self.clock()
            previous_check = state.get("checked_through") or state["updated_at"]
            if previous_check and state["schedules"] and now - timestamp(previous_check) > timedelta(days=31):
                state["history_gap"] = state.get("history_gap") or {"after": previous_check, "before": (now - timedelta(days=31)).isoformat()}
            value = self._apply(state, command, now)
            # Materialize overdue unclaimed occurrences so they cannot vanish when
            # the 31-day evaluation window advances. Never mark notifications sent.
            for rid, item in expected(state, now).items():
                if rid in state["runs"] or now <= timestamp(item["due_at"]) + timedelta(minutes=item["schedule"]["start_grace_minutes"]):
                    continue
                state["runs"][rid] = {**item, "status": "missed", "finished_at": now.isoformat(),
                    "report": {"status": "failed", "summary": "The scheduled review did not start before its deadline.",
                               "coverage": [], "findings": [], "recommendations": [], "errors": ["MISSED_RUN: inspect the host task and connector availability."]},
                    "delivery": {"status": "pending", "receipt": None}}
            state["checked_through"] = now.isoformat()
            # Retain unresolved findings; remove old resolved findings and delivered runs only.
            cutoff = now - timedelta(days=90)
            state["runs"] = {k: v for k, v in state["runs"].items()
                             if timestamp(v["due_at"]) >= cutoff or v["delivery"]["status"] != "accepted"}
            state["findings"] = {k: v for k, v in state["findings"].items()
                                 if v["resolution"] is None or timestamp(v["last_seen_at"]) >= cutoff}
            state["revision"] += 1
            state["updated_at"] = now.isoformat()
            encoded = json.dumps(state, allow_nan=False)
            if len(encoded.encode()) > MAX_BYTES or len(state["runs"]) > 1000 or len(state["findings"]) > 1000:
                raise RequestError("REVIEW_STORAGE_FULL")
            self.store.save(encoded)
            return {"revision": state["revision"], "operation": command.operation, **value,
                    "garmin_request_sent": False, "notification_sent": False}

    def _apply(self, state, command, now):
        if isinstance(command, Delete):
            revision = state["revision"]
            state.clear()
            state.update(version=1, revision=revision, updated_at=None, checked_through=None, history_gap=None, profile=None, schedules=[], runs={}, findings={})
            return {"deleted": True, "host_tasks_cancelled": False}
        if isinstance(command, AcknowledgeGap):
            acknowledged = state.get("history_gap")
            state["history_gap"] = None
            state["gap_acknowledgement"] = {"gap": acknowledged, "answer": command.acknowledgement, "at": now.isoformat()}
            return {"acknowledged_gap": acknowledged}
        if isinstance(command, Recover):
            run = state["runs"].get(command.run_id)
            if run is None or run["status"] != "running" or now <= timestamp(run["deadline_at"]):
                raise ValueError("Only an expired running claim can be recovered")
            run.update(status="failed", finished_at=now.isoformat(),
                       report={"status": "failed", "summary": "The review worker did not finish before its deadline.",
                               "coverage": [], "findings": [], "recommendations": [], "errors": ["RUN_DEADLINE_EXCEEDED: inspect the host run; do not assume checks completed."]})
            return {"run_id": command.run_id, "status": "failed", "delivery": "pending"}
        if isinstance(command, Configure):
            current = [v for v in state["schedules"] if v["until"] is None]
            if len(current) >= 10 and not any(v["schedule"]["schedule_id"] == command.schedule.schedule_id for v in current):
                raise ValueError("At most ten review schedules")
            for epoch in current:
                if epoch["schedule"]["schedule_id"] == command.schedule.schedule_id:
                    if epoch["schedule"] == command.schedule.model_dump() and epoch["host_task_id"] == command.host_task_id:
                        return {"configured": True}
                    epoch["until"] = now.isoformat()
            if len(state["schedules"]) >= 100:
                raise RequestError("REVIEW_STORAGE_FULL")
            state["schedules"].append({"schedule": command.schedule.model_dump(), "host_task_id": command.host_task_id,
                                       "since": now.isoformat(), "until": None})
            return {"configured": True, "host_schedule_created": False}
        if isinstance(command, SaveProfile):
            state["profile"] = command.profile.model_dump()
            return {"profile_saved": True}
        if isinstance(command, Start):
            due = timestamp(command.due_at)
            rid = run_id(command.schedule_id, due)
            if rid in state["runs"]:
                return {"claimed": False, "run_id": rid, "status": state["runs"][rid]["status"]}
            item = expected(state, now).get(rid)
            if item is None:
                raise ValueError("Not an expected due occurrence in the preceding 31 days")
            if any(r["status"] == "running" and r["schedule_id"] == command.schedule_id
                   and timestamp(r["deadline_at"]) > now for r in state["runs"].values()):
                raise RequestError("REVIEW_RUN_BUSY")
            claim = secrets.token_hex(16)
            local_day = due.astimezone(ZoneInfo(item["schedule"]["timezone"])).date()
            end = local_day if item["template"] == "workout_preparation" else local_day - timedelta(days=1)
            begin = end - timedelta(days=6) if item["template"] == "weekly_review" else end
            window = {"start_date": begin.isoformat(), "end_date": end.isoformat(), "timezone": item["schedule"]["timezone"]}
            state["runs"][rid] = {**item, "status": "running", "started_at": now.isoformat(),
                                   "deadline_at": (now + timedelta(minutes=item["schedule"]["deadline_minutes"])).isoformat(),
                                   "claim_token": claim, "review_window": window, "report": None, "delivery": {"status": "pending", "receipt": None}}
            return {"claimed": True, "run_id": rid, "claim_token": claim,
                    "deadline_at": state["runs"][rid]["deadline_at"],
                    "review_window": window,
                    "late": now > due + timedelta(minutes=item["schedule"]["start_grace_minutes"])}
        if isinstance(command, Finish):
            run = state["runs"].get(command.run_id)
            if run is None or not secrets.compare_digest(run.get("claim_token", ""), command.claim_token):
                raise RequestError("REVIEW_CLAIM_REQUIRED")
            report = command.report.model_dump()
            if any(v.fetched_at and timestamp(v.fetched_at) > now for v in command.report.coverage):
                raise ValueError("Report source fetch times cannot be in the future")
            if command.report.status != "failed":
                configured = set(run["schedule"]["sources"])
                supplied = {v.source for v in command.report.coverage if v.status != "not_configured"}
                if not configured <= supplied:
                    raise ValueError("Report must explicitly cover every configured source, including unavailable sources")
            if run["status"] != "running":
                if run["report"] == report:
                    return {"run_id": command.run_id, "status": run["status"], "already_saved": True}
                raise RequestError("REVIEW_STATE_CONFLICT")
            if now > timestamp(run["deadline_at"]) and command.report.status != "failed":
                raise ValueError("Expired run must finish with a failed report explaining the timeout")
            run.update(status=command.report.status, report=report, finished_at=now.isoformat())
            for finding in command.report.findings:
                payload = finding.model_dump()
                digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
                previous = state["findings"].get(finding.finding_id)
                if previous and previous["evidence_hash"] == digest:
                    previous["last_seen_at"] = now.isoformat()
                    continue
                state["findings"][finding.finding_id] = {"finding": payload, "evidence_hash": digest,
                    "last_seen_at": now.isoformat(), "resolution": None, "answer": None,
                    "previous_resolution": previous["resolution"] if previous else None}
            return {"run_id": command.run_id, "status": run["status"], "delivery": "pending"}
        if isinstance(command, Delivery):
            run = state["runs"].get(command.run_id)
            if run is None or run["status"] == "running":
                raise ValueError("Persist a terminal report before recording delivery")
            run["delivery"] = {"status": command.status, "receipt": command.receipt, "recorded_at": now.isoformat()}
            return {"run_id": command.run_id, "delivery": command.status, "receipt_is_caller_reported": True}
        if isinstance(command, Resolve):
            item = state["findings"].get(command.finding_id)
            if item is None:
                raise ValueError("Unknown finding")
            item.update(resolution=None if command.resolution == "reopen" else command.resolution,
                        answer=command.answer, resolved_at=now.isoformat())
            return {"finding_id": command.finding_id, "resolution": item["resolution"], "account_corrected": False}
        raise ValueError("Unsupported review operation")
