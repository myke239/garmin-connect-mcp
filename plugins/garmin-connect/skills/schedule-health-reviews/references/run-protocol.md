# Scheduled review execution

1. Read `get_garmin_review_state(section="overview")`. Check the matching schedule,
   confirmed profile, current revision and due occurrences. Follow pagination for
   unresolved findings and relevant reports. If state access fails, issue a visible
   failed-run response with the safe error code and remediation; never end silently.
2. Claim the exact occurrence with `update_garmin_review_state` operation `start`,
   `schedule_id`, `due_at` and `expected_revision`. Retain its `claim_token` and
   `deadline_at`. If `claimed=false`, do not duplicate collection or delivery;
   inspect the existing report. On revision conflict, reread and reconcile. Never
   guess a token, overwrite another worker or keep retrying a busy run.
3. Collect configured domains independently. Prefer existing evidence; fetch
   baseline history in small bounded batches (14-28 prior observations when
   useful). Do not refetch an entire history every day. Track source date,
   fetch time, measurement time if available, coverage and units. A fresh fetch
   does not prove a recent sensor measurement. Do not carry forward old values
   as today's. Stop before the deadline, leaving time to persist/report.
4. Stop repeated calls to a source on authentication, permission or rate limits.
   Respect retry-after and existing tool retries; never multiply retries in a
   loop. Continue independent providers. Classify coverage as available, partial,
   unavailable or not_configured; failed configured sources need a reason.
   If a tool times out or an input fails, record the failed stage and continue
   only checks with sufficient independent evidence. No waiting for user input
   inside an unattended run; questions belong in the finished report.
5. Use the template's workflow. `daily_logs` examines yesterday in the schedule's
   timezone; `workout_preparation` examines remaining sessions today; weekly
   review examines seven completed days. A late preparation run must recheck
   start/completion and label missed preparation; never deliver expired meal or
   nap advice as timely. A late log review can explicitly report its catch-up
   window. No invented backdated as-of snapshots.
6. Persist `finish`: completed/partial/failed, concise summary, configured-source
   coverage, findings, recommendations and safe errors. No usable evidence means
   failed; incomplete expected coverage means partial. An expired claim may only
   finish failed with an explanation. `failed` can use empty coverage when an
   early failure prevented collection. Every run gets a report, including rest
   days and zero discrepancies. On storage failure, return the report plus the
   storage error visibly so the host still has a result.
7. Return the saved report in the requested host destination. Compose the user's
   answer with review dates/timezone, assessment, key evidence/freshness, missing
   sources, actionable suggestions and prioritized clarification questions.
   Begin with at most three consequential questions, but preserve all findings.
   Do not promise to have sent an independent notification.
8. Record `delivery` only when the host supplies an actual acceptance receipt or
   the user explicitly acknowledges the report. Without either, leave pending;
   the monitor will report DELIVERY_UNCONFIRMED. Record actual delivery failures.
   Retry delivery of the saved report rather than recollecting data. A receipt
   means accepted, not read. The plugin records caller-reported receipts and
   cannot independently verify an external delivery service.

## Clarifications

Stable finding IDs allow answers to refer to a precise date and record. Resolve
as correct_as_recorded, missing_entry, intentional_exception, routine_changed,
dismissed or corrected. Store the actual answer; no response is not confirmation.
Identical evidence retains resolution. Changed evidence reopens the finding.
Do not repeatedly ask a resolved question; consolidate unresolved questions into
the current review. A routine_changed resolution alone does not edit the profile:
save the newly confirmed routine separately. corrected requires observed readback
or user-confirmed correction, never just a proposed fix.

When authorized to correct a record, use the provider's existing guarded workflow,
fresh targets and verified units. Preserve unrelated fields. Handle unsupported
food writes explicitly. Uncertain write outcomes must not be retried as new intents.

## Monitoring deployment contract

Run the installed launcher `review-monitor --once` from an independent supervisor
that can read the connector's private ledger. Exit 0 means no detected alerts,
1 means missed/expired/undelivered runs (or no schedules), and 2 means the monitor
itself could not inspect state. Output is bounded JSON without profile or report
content. Without `--once`, the command emits a heartbeat every 60 seconds (configurable
10-3600) and remains running. The supervisor must alert on missing heartbeat/process
failure, not just JSON alerts. Never discard a nonzero exit or failed read as
"nothing to report". Do not place secrets or health reports in notification logs.

A supervisor on another host can instead poll `get_garmin_review_state` via the
authenticated connector and alert on failed access as well as `monitor.alerts`.
It must independently expect a schedule/check even when the connector is offline.
The plugin does not provision this host or send email/webhooks. Configure a real
delivery integration with explicit user intent and test it by inducing a missed
run, stalled run, delivery failure and connector outage before claiming reliability.

History evaluation is bounded to 31 days; a longer gap is reported explicitly.
Subsequent updates persist overdue missing occurrences as failed/missed reports.
An interrupted worker's expired claim can be closed with `recover`; its failure
report still needs delivery. Acknowledge a reported historical gap only after
reviewing it with the user; acknowledgement never means missing work succeeded.
Delivered runs/resolved findings may be pruned after 90 days; undelivered reports
and unresolved questions remain, subject to bounded storage. Capacity failure
must be surfaced and resolved, never handled by discarding unanswered findings.
