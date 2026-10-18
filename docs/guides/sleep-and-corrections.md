# Sleep, naps and record corrections

[Documentation home](../README.md) · [Write workflow](account-writes.md) · [Coverage and research gates](../development/write-coverage.md)

Version 0.18.0 adds eleven guarded operations and four discovery/target tools.
Start with `get_garmin_capabilities(resource="all")` to discover registered writes,
local policy, profile visibility, remote grant and the target reader. Candidates
listed there are research items, not callable operations. Discovery is offline.

These contracts were traced through Garmin Connect Android 5.30.1 and the pinned
SDK, with offline transport tests. Saved-account GETs confirmed sleep and weight
response shapes. **The new mutations have not been live-tested.** A successful
offline test is not proof that Garmin accepts every account/date/device variant.

## Main sleep

1. Read `get_garmin_sleep_mutation_target(calendar_date="YYYY-MM-DD")` freshly.
2. Query `get_garmin_write_schema(operation)` for the selected operation.
3. Prepare the exact parameters and a stable intent key; review the complete
   preview within the user's authorized scope; commit the returned draft ID.
4. Inspect journal verification and fetch a fresh target. Do not retry an
   `unknown`/`in_progress` result with a different intent key.

| Operation | Parameters and behavior |
| --- | --- |
| `add_sleep` | An **absent** target's date/hash, `start_time`, `end_time`, `time_zone`. Creates manual duration only; no inferred stages or score. Refuses an existing sleep record. Main sleep cannot normally be deleted, so do not create disposable synthetic sleep in a real account. |
| `update_sleep_times` | Existing `sleep_id`, date/hash and start/end/zone. Patches native GMT endpoints, elapsed duration and confirmed flag in a fresh native DTO. Preserves the original local timestamp fields, confirmation type, stages, scores, notes and other recorded metadata, matching the Android save flow. |
| `set_sleep_note` | Existing ID/date/hash and nonempty `note` (connector bound 2,000 characters). Replaces that night's entire note. |
| `clear_sleep_note` | Existing ID/date/hash. Deletes only the note; it does not delete sleep. |

The date is the local **wake/end date**. Write times are whole-second ISO 8601
strings with explicit offsets, e.g. `2026-10-16T23:00:00-07:00`, plus an IANA zone
such as `America/Los_Angeles`. This is an illustrative timestamp, not a requested
account edit. A window must have finished, last 1 minute to 24 hours and end on
the selected date. Offsets must match the zone: explicit fallback offsets select
the occurrence, while nonexistent spring-forward times are rejected. Elapsed
duration is computed in UTC. Target-read endpoints are Unix **milliseconds**;
do not pass them as write timestamp strings.

Garmin owns score/stage recalculation. Readback verifies stored GMT endpoints and
confirmed flag, or note value/absence; it does not promise recalculated scores,
Sleep Coach changes or watch sync. Editing an older night can affect Garmin
features differently. The usual device bedtime/wake schedule is a separate
setting and has no registered setter here.

## Naps

Read `get_garmin_nap_mutation_target(calendar_date, time_zone)` for the current
local day. It lists all returned naps, including overlaps, with original
`nap_start_ms`/`nap_end_ms` identity and the **full-list** hash. Use schemas for
`add_nap`, `update_nap` or `delete_nap`. Update/delete target the original start;
the worker also preserves the original end in the update URL. Do not use a new
start time as the original identity.

Naps must have finished, fall entirely within the current local calendar day,
last 5 minutes to 3 hours and overlap neither main sleep nor another nap. The
day restriction is checked at preparation, preflight and immediately before
send. A midnight crossing can reject a previously prepared intent. Creation
requires an existing main-sleep DTO to supply native account/device context.
An unavailable context fails rather than guessing a device. Missing native
sleep-need device ID uses Android's native zero sentinel, not a selected watch.

Input offsets must match the IANA zone. Native nap timestamps are UTC strings
without a suffix; native offsets are **minutes**, not seconds or hours. The
worker handles this conversion and uses Garmin's manual-Connect source enum.
Existing device/feedback metadata is retained on edit. Deletion also needs
`confirm_delete=true`. Fresh readback verifies the saved interval or absence;
historical erasure and device synchronization are not established.

## Exact deletion and hydration correction

Read `get_garmin_record_mutation_target` with these arguments:

| Kind | Reader arguments | Operation |
| --- | --- | --- |
| `activity` | `record_id` only | `delete_activity` with activity ID, exact old name, full-record hash and `confirm_delete=true` |
| `weight` | `calendar_date` only | `delete_weight_measurement` with one returned `record_id`, its hash, date and `confirm_delete=true` |
| `blood_pressure` | `calendar_date` only | `delete_blood_pressure_measurement` with one returned version ID/hash, date and `confirm_delete=true` |
| `hydration` | `calendar_date` only | `adjust_hydration` with dated hash, explicit-offset timestamp and signed `value_in_ml` |

Do not guess identity from timestamp, array order or an average. Weight's exact
day-view `samplePk` is passed to Garmin's `byversion` route; BP uses its native
`version`. Multiple same-day measurements remain separate targets. Date binding
and fresh content checks reject stale/unsupported shapes before mutation.

Deletion removes the **entire** selected record. Weight deletion includes
attached body-composition fields; it is not a way to clear one composition
value. No bulk deletion or delete-and-recreate edit is exposed. Activity
deletion retains any opted-in local archive. Readback establishes current
endpoint absence, not erasure across backups, integrations or physical devices.

Hydration correction is a nonzero signed delta between -10,000 and +10,000 ml.
The timestamp's local date must match the selected day. The fresh daily total
must remain nonnegative. A null total is unavailable, not zero: the target
reports no correction operation until a recorded total exists; actual positive
intake can use add_hydration. `add_hydration` retains its original positive-only
contract. There is no per-drink identity or arbitrary overwrite/delete API.
Readback checks the expected total; concurrent external changes can produce an
unconfirmed result. Never add a compensating delta automatically.

## Verification and concurrency

New commits add `verification` metadata. `transport_accepted` means the older
operation returned; `stored_value_verified` means the new operation's specified
fresh-read checks passed; `catalog_absence_verified` is a Lifestyle catalog
claim only. Unknown results remain unknown. Existing journal entries retain
their original status/result and return null verification if none was recorded.
Device sync and historical erasure remain separate, unverified claims.

Hashes are bounded canonical snapshots, checked again in serialized preflight.
They prevent applying a reviewed intent to changed data. Garmin has no verified
conditional-write token here: another client can still edit between final read
and mutation. These are guarded writes, not transactional compare-and-swap.

## Sources

- [Garmin sleep editing](https://support.garmin.com/en-IN/?faq=mBRMf4ks7XAQ03qtsbI8J6)
- [Garmin nap editing](https://support.garmin.com/en-GB/?faq=2icqqZFq3YAX5K9VGU2CQ9&productID=873008&tab=)
- [Garmin hydration controls](https://support.garmin.com/en-ZA/?faq=390puZ3AgO4hM3IzakFs99&productID=707538&tab=topics)
- [Pinned SDK 0.3.17](https://github.com/cyberjunky/python-garminconnect/blob/v0.3.17/garminconnect/__init__.py)

Native Android evidence: sleep interface `im1.a`, nap reader `fs1.a`, DTOs
`km1.v`/`km1.b`, sleep copy call `b21.k`, nap body builder `pn1.a` and weight
interface `m42.a`. Only derived contract notes are committed; no app binaries,
decompiled sources or personal payloads are shipped.
