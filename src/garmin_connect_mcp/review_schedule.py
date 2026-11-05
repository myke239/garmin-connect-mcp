"""Portable civil-time schedules and host prompts. Does not create host automations."""
import hashlib
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from .review_models import ReviewSchedule, timestamp

SKILLS = {"daily_logs": "review-daily-logs", "workout_preparation": "daily-performance-coach",
          "weekly_review": "review-training-recovery"}


def occurrence(schedule, day):
    schedule = ReviewSchedule.model_validate(schedule)
    anchor = date.fromisoformat(schedule.start_date)
    if not schedule.enabled or day < anchor:
        return None
    if schedule.frequency == "daily":
        matches = (day - anchor).days % schedule.interval == 0
    else:
        monday = anchor - timedelta(days=anchor.weekday())
        matches = ((day - monday).days // 7) % schedule.interval == 0 and day.weekday() in schedule.weekdays
    if not matches:
        return None
    naive = datetime.combine(day, time.fromisoformat(schedule.local_time))
    zone = ZoneInfo(schedule.timezone)
    # First fold on a repeated wall time; shift a missing wall time to first valid minute.
    for minutes in range(181):
        candidate = (naive + timedelta(minutes=minutes)).replace(tzinfo=zone, fold=0)
        utc = candidate.astimezone(UTC)
        if utc.astimezone(zone).replace(tzinfo=None) == candidate.replace(tzinfo=None):
            return utc
    raise ValueError("Timezone transition exceeds supported three-hour adjustment")


def run_id(schedule_id, due):
    return hashlib.sha256(f"{schedule_id}|{due.astimezone(UTC).isoformat()}".encode()).hexdigest()[:24]


def build_schedule(schedule, as_of):
    schedule = ReviewSchedule.model_validate(schedule)
    now = timestamp(as_of)
    today = now.astimezone(ZoneInfo(schedule.timezone)).date()
    next_runs = []
    for offset in range(900):
        due = occurrence(schedule, today + timedelta(days=offset))
        if due is not None and due > now:
            next_runs.append({"run_id": run_id(schedule.schedule_id, due), "due_at": due.isoformat(),
                              "local_time": due.astimezone(ZoneInfo(schedule.timezone)).isoformat()})
            if len(next_runs) == 3:
                break
    focus = {
        "daily_logs": "Review yesterday's completed local calendar day. Check food, strength sets, activities, confirmed routines and other configured entries. Recheck unresolved questions when evidence changes.",
        "workout_preparation": "Review today's remaining planned workouts. Distinguish current readings from morning snapshots. Give conditional food, hydration, rest and workout suggestions appropriate to the time remaining; report completed workouts and rest days.",
        "weekly_review": "Review the preceding seven completed local calendar days, trends, unresolved logging issues and comparable workout outcomes. Separate observations from coaching judgment.",
    }[schedule.template]
    prompt = (f"Use the Garmin Connect {SKILLS[schedule.template]} skill and the scheduled-run protocol in schedule-health-reviews. "
              f"This is review schedule {schedule.schedule_id}, timezone {schedule.timezone}. "
              "Read get_garmin_review_state first and claim the due run with update_garmin_review_state before collecting data. "
              f"{focus} Use confirmed profile and connected sources; missing or unavailable data stays unknown. "
              "Collect sources independently within the run deadline; stop calls to a source on authentication, permission or rate-limit errors. "
              "Persist a completed, partial or failed report with coverage and unresolved questions, even when nothing needs attention or all sources fail. "
              "If state storage fails, still return a visible failure explaining the failed stage. Return the report in this conversation. "
              "Do not claim notification delivery without an actual delivery receipt. Do not change health records from inferred corrections.")
    return {"schedule": schedule.model_dump(), "next_runs": next_runs, "prompt": prompt,
            "host_schedule_created": False, "monitor_installed": False,
            "dst_policy": "First occurrence of ambiguous time; nonexistent time moves to first valid minute within three hours.",
            "requirements": ["Create or update the host's task with these exact civil-time semantics; verify its next run.",
                             "Keep the source connector reachable from the execution environment.",
                             "An independent supervisor must poll review-monitor and alert on nonzero exit or missing heartbeat.",
                             "Register the schedule only after host creation succeeds; retain the host task ID.",
                             "Never represent this prompt or monitor command as an installed scheduler or notification service."]}
