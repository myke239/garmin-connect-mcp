# Scheduled health reviews

[Documentation home](../README.md) · [Coaching evidence](coaching.md)

Ask the plugin to review yesterday's logs every morning, help prepare for today's
workouts before exercise, or review the previous week. The `schedule-health-reviews`
skill prepares the workflow and uses the host's scheduling tools. Frequency/time
and a confirmed timezone are normally enough to start; missing nutrition or
workout details reduce specificity and are reported explicitly.

## Templates and current capability

| Template | Suggested cadence | Workflow |
| --- | --- | --- |
| Daily log review | Daily, 08:00 after sync | Food totals/completeness, unknown exercises, comparable-set deviations, confirmed routines and other observed gaps |
| Workout preparation | Daily, noon for evening exercise | Existing recovery and strength analysis plus food/rest/hydration options for remaining sessions |
| Weekly review | Weekly before planning | Seven completed local days, comparable outcomes, trends and unresolved logging questions |

The new log analyzer produces questions, never account corrections. A 1,000 kcal
log against a 2,000 kcal goal is not a measured energy deficit. Unknown strength
load units are excluded from numeric comparisons. Warmup/drop sets and intentional
variation are excluded. A missing supplement entry is unknown, not a missed dose.
The 0.7 calorie-goal ratio and 0.25 load-deviation ratio are adjustable logging
heuristics, not medical thresholds. Expected meals and duplicate-entry candidates
come from bounded source inspection and confirmed routines, not automatic guesses.

Workout preparation reuses the existing coaching tools. It is not a calibrated
performance forecast. The collector currently returns morning readiness; a fresh
fetch does not turn it into a noon measurement. Current Body Battery mapping is
not normalized. Meal timing, consumed versus planned food, symptoms and workout
start time must be confirmed before precise timing advice. Food-entry access
depends on the user's connected nutrition provider.

## Tools and setup

`get_garmin_review_guide` supplies nested schemas and synthetic examples.
`build_garmin_review_schedule` returns a reusable prompt and the next three due
times; **it creates no host task**. Use the host's actual scheduler, verify its
next occurrence, then register that task's ID with `update_garmin_review_state`.
Garmin workout-calendar tools cannot schedule agent reviews.

Schedules support daily intervals 1-30 days or selected weekdays at intervals
1-30 weeks, with a start date and IANA timezone. A repeated DST time uses its first
occurrence. A nonexistent time moves to the first valid minute within three hours.
The host must support the same semantics; setup must disclose/resolve differences.
Changing a schedule retains old expected occurrences and outstanding reports.

`get_garmin_review_state` returns confirmed context, due runs, monitor status, or
paginated runs/findings. `update_garmin_review_state` uses a required current
revision and fixed operations: configure, profile, start, finish, delivery,
resolve, recover, acknowledge_gap and delete. Run claims are exclusive; repeat
starts return `claimed=false`. The original claim token fences completion.
`recover` turns only an expired running claim into an explicit failed report,
preventing a stalled worker from later claiming success.

Profile routines contain confirmed expectations, not dated consumption. Questions
have stable IDs, retain answers for unchanged evidence, and reopen when evidence
changes. Resolving a question does not edit Garmin, a nutrition diary or the
profile. Actual corrections use the existing provider write workflow.

## Failure and delivery contract

Every started run must persist completed, partial or failed, including zero-findings
and rest-day reports. Missing configured-source coverage cannot claim completed.
No usable data requires failed with an explanation. Source failures remain
independent; a food connector outage does not erase usable Garmin evidence.
An expired run can only finish failed. If persistence itself fails, the agent must
still return a visible host response explaining the stage/error.

Execution and delivery are separate. A saved report is pending until an actual
host receipt or explicit user acknowledgement is recorded. Receipts are
caller-reported; the plugin does not independently verify another service.
Delivery retries should reuse the saved report. Default start, execution and
delivery grace periods are each 15 minutes and are configurable within bounds.
Late preparation must recheck remaining sessions rather than issue expired advice.

**The plugin does not provide an always-on scheduler or outbound notification
service.** A skill cannot detect that its own run never started. Strict missed-run
alerting requires an independent supervisor and configured delivery route. Local
host outages also affect cloud agents if the connector is tunneled from that host.

Run the installed launcher:

```text
garmin-connect review-monitor --once
```

The launcher name depends on installation (`garmin-connect.exe` or its installed
wrapper); source development can use `python -m garmin_connect_mcp.review_monitor`.
The monitor emits bounded JSON containing IDs/status only, no health reports.
Once mode exits 0 for no detected alerts, 1 for review alerts/no schedules, and 2
when the monitor itself cannot inspect storage. Without `--once`, it emits a
heartbeat every 60 seconds; `--interval` accepts 10-3600 seconds. A supervisor
must alert on missing heartbeat/nonzero exit as well as alert codes. No message
is sent by this command. An independently hosted service may instead poll the
authenticated state tool and alert on failed access as well as reported alerts.

| Alert | Meaning/action |
| --- | --- |
| MISSED_RUN | No claim by the start deadline; inspect host task and connector |
| RUN_DEADLINE_EXCEEDED | Worker failed to finish; recover the expired claim and deliver its failure report |
| DELIVERY_UNCONFIRMED | Report saved but no acceptance evidence; inspect destination or obtain acknowledgement |
| DELIVERY_FAILED | Actual reported delivery error; retry the saved report |
| HISTORY_WINDOW_EXCEEDED | Gap exceeds 31-day expected-run evaluation; inspect history before explicitly acknowledging the gap |
| REVIEW_MONITOR_FAILED | Monitor/storage failure; supervisor must alert rather than treating it as healthy |

Unclaimed overdue occurrences are saved as missed during subsequent ledger
updates, so undelivered misses remain visible beyond the evaluation window.
Longer unobserved gaps remain explicit until acknowledged; acknowledgement does
not claim the missing reviews ran. Test missed starts, process interruption,
failed delivery and connector outage before describing an installation as monitored.

## Privacy, policy and retention

The private ledger lives in `reviews` under the configured Garmin data directory,
outside source control. It uses the existing store: Windows DPAPI and owner/SYSTEM
ACLs; Linux owner-only permissions or explicitly configured Secret Service
encryption. No raw-food archive or credentials are added to the ledger. User-facing
profile text, report excerpts and answers are personal data. Export desired data
through paginated reads before deletion.

Global `writes-disable` blocks private review mutations too. Local review policy
is separate from Garmin account-operation policies and is controlled with:

```text
garmin-connect reviews-status
garmin-connect reviews-disable
garmin-connect reviews-enable --operations configure profile start finish delivery resolve recover acknowledge_gap delete
```

`--operations` with no values denies all review mutations. Enabling reviews does
not override global write disable. Remote mutations also require `garmin:write`.
The read-only discovery profile omits the mutation tool. Read/monitor access
continues after write disable so failures remain inspectable. Disabling writes
does not cancel host schedules; pause those separately when appropriate.

State bounds: ten current schedules, 100 configuration epochs, 1,000 runs,
1,000 findings and 4 MiB. Delivered runs and resolved findings older than 90 days
are pruned on updates; undelivered/unresolved records are retained. Capacity
failure is explicit, not silent deletion. `delete` requires confirmation and
clears private review state, but cannot cancel host tasks or erase external
conversation copies. Cancel schedules first. No claim of physical secure erasure
is made.
