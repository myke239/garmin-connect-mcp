---
name: schedule-health-reviews
description: Configure recurring Garmin and nutrition log reviews, daily workout preparation, or weekly training reviews with host scheduling, persistent questions and explicit failure reporting. Use for agent check-ins, not Garmin workout-calendar scheduling.
---

# Schedule health reviews

Use `get_garmin_review_guide` for installed schemas, templates and executable
synthetic examples. Examples are not the user's records. Available templates:
`daily_logs` (recommend morning after sync), `workout_preparation` (recommend
before exercise, noon for evening sessions), and `weekly_review`.

## Configure

Discover the host's scheduling tools and connected Garmin/nutrition sources.
Reuse the user's requested cadence, timezone and established preferences. Ask
only for missing information that prevents setup: usually time/frequency and an
unambiguous IANA timezone. Discover workout time where possible; a calendar date
is not a start time. Configure daily intervals or weekly weekdays (Monday=0).
Set `sources` to the domains this task is expected to check; disclose omitted
domains. An expected but disconnected source should remain configured so failure
is visible. Never quietly narrow the requested task to make a run successful.

Read `get_garmin_review_state` and matching host tasks before creating duplicates.
Check its `local_operation_policy` and `remote_write_grant_present`: scheduled
ledger use needs configure/start/finish/delivery, and resolve for follow-up answers.
Verify the mutation tool is exposed. Resolve denied permissions or explicitly
report setup incomplete before creating a task that cannot record its outcomes.
Save only user-confirmed profile/routines with `update_garmin_review_state`;
routine amounts require confirmed units. This is private persistent health context;
explain its storage and retention during setup. Do not infer a mandatory habit
from frequency alone. Routine changes are separate from dated consumption.

Build with `build_garmin_review_schedule`, using current offset-aware `as_of`.
The returned prompt and next runs are a draft, not a created task. Test the
selected workflow once with the available sources. A partial test can support
setup if the user accepts its clearly disclosed coverage; do not claim success
for unavailable checks. A failed preflight must be reported, not hidden.

Use the host's actual scheduling tool when creation is authorized. Prefer an
ongoing coaching chat when supported; honor a requested standalone destination.
Copy the returned skill-driven prompt and configure the matching cadence and
timezone. Verify the host's next occurrence against the builder. If DST or
interval semantics differ, resolve the mismatch before claiming setup complete.
Then `configure` the ledger with the actual host task ID and schedule. If ledger
registration fails, report the host task ID and repair or pause that exact task;
do not leave an unmonitored task described as fully configured.

Host scheduling may be local or cloud. Verify every source is reachable there:
a cloud agent with a connector tunneled from a powered-off PC cannot read Garmin.
Do not use `schedule_workout` to schedule agent work. If the host cannot schedule,
return the prepared template and explain the missing capability; do not claim
creation or install an alternative scheduler without user intent.

## Reliability and subsequent runs

Read [run protocol](references/run-protocol.md) for every unattended review and
for monitoring setup. A visible result is mandatory even with no findings or no
usable data. A prompt cannot detect its own failure to start. Strict missed-run
notification requires an independent supervisor that checks the monitor and its
heartbeat, plus an explicitly configured delivery route. Do not describe a
second task on the same offline host as independent monitoring.

The plugin supplies `review-monitor`, not a notification service. Where an
external supervisor is not connected, disclose **monitoring not configured**;
the host schedule alone cannot satisfy guaranteed missed-run alerting. Do not
mark notification acceptance merely because an assistant response was composed.

For updates, change and verify the existing host task before updating its ledger
configuration. Pause both host and ledger when requested. Pause does not erase
outstanding reports. Deletion of private review state requires explicit intent;
cancel relevant host tasks first. Existing Garmin write permissions are not
authorization to correct inferred health records.
