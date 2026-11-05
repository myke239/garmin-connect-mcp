"""Review discovery with executable synthetic examples and honest host boundaries."""
NAMES = {"build_garmin_review_schedule", "analyze_garmin_daily_logs", "get_garmin_review_state", "update_garmin_review_state"}


def guide(schemas):
    return {
        "version": 1,
        "templates": [
            {"template": "daily_logs", "skill": "review-daily-logs", "suggested_time": "08:00", "frequency": "daily"},
            {"template": "workout_preparation", "skill": "daily-performance-coach", "suggested_time": "12:00", "frequency": "daily"},
            {"template": "weekly_review", "skill": "review-training-recovery", "suggested_time": "09:00", "frequency": "weekly"}],
        "input_schemas": schemas,
        "workflow": [
            "Use schedule-health-reviews for setup; discover host scheduling and data connectors before creating tasks.",
            "Confirm source identity/timezone and save only user-confirmed routines/profile.",
            "Build a portable schedule and test the review manually. The builder creates no host task.",
            "Create/update the actual host task, verify its next occurrence, then register its ID with configure.",
            "Each unattended run reads state, claims one due occurrence, collects independent sources, and persists a report before delivery.",
            "Finish with failed status and a safe explanation even if every source fails; storage failure still requires a visible host response.",
            "Use existing recovery/strength tools for workout preparation; review data-quality findings before interpreting totals.",
            "Record delivery only with a host receipt or explicit user acknowledgement, never merely because a response was composed.",
            "An independent supervisor must consume review-monitor output and detect both alerts and missing heartbeats."],
        "limits": {"lookback_days": 31, "retention_days": 90, "max_runs": 1000, "max_findings": 1000,
                   "max_schedules": 10, "unresolved_and_undelivered_retained": True, "max_state_bytes": 4194304},
        "boundaries": [
            "No built-in host scheduler, outbound notification transport, medical clearance, or health-record writes.",
            "Monitoring cannot run or alert from a powered-off host; use an independently hosted supervisor.",
            "Current Garmin collector provides morning readiness, not verified noon readiness or current Body Battery.",
            "Nutrition entry details require the caller's connected nutrition provider; no alternate client or credential sharing.",
            "Private ledger mutations require garmin:write remotely and honor global disable plus local review-operation policy.",
            "State uses existing protected storage: DPAPI on Windows, owner-only or configured Secret Service on Linux.",
            "Thresholds are logging heuristics. Unknown weight units, intake and symptoms must not be guessed."],
        "examples_are_synthetic": True,
        "examples": [
            {"tool": "build_garmin_review_schedule", "arguments": {
                "schedule": {"schedule_id": "demo-morning", "template": "daily_logs", "timezone": "America/Los_Angeles",
                             "local_time": "08:00", "start_date": "2026-01-01"}, "as_of": "2026-01-02T07:00:00-08:00"}},
            {"tool": "analyze_garmin_daily_logs", "arguments": {"evidence": {
                "calendar_date": "2026-01-01", "timezone": "America/Los_Angeles", "as_of": "2026-01-02T08:00:00-08:00",
                "coverage": [{"source": "nutrition", "status": "available", "fetched_at": "2026-01-02T07:59:00-08:00"},
                             {"source": "lifestyle", "status": "available", "fetched_at": "2026-01-02T07:59:00-08:00"}],
                "diary": {"complete": False, "calories_kcal": 1000, "goal_kcal": 2000},
                "routines": [{"routine_id": "demo-routine", "label": "Example confirmed habit", "confirmed": True, "recorded": "missing"}]}}}],
    }
