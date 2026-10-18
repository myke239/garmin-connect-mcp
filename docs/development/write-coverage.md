# Write coverage and remaining contract gates

[Documentation home](../README.md) · [Sleep and corrections](../guides/sleep-and-corrections.md)

The runtime registry in `capabilities.py` maps every exposed tool to resources
and every registered operation to a write capability. Offline tests assert exact
tool and operation coverage, including profiles and policy. Version 0.18.0 has
58 default tools and 37 allowlisted operations. Registration is not a promise
of live acceptance for every account or device.

## Implemented foundations and corrections

- Offline `get_garmin_capabilities` exposes writes, current local policy, profile
  visibility, remote grant, schema/target readers and explicit unsupported areas.
- Bounded canonical snapshot hashes and fresh preflight are shared by the new
  operations. Existing operation names, parameters and journal statuses remain.
- New commit results distinguish transport return, specified stored-value
  readback, catalog absence and unknown outcomes. Physical sync is separate.
- Main sleep: absent-record manual add, time update, note replacement/clear.
- Current-day naps: full target/list discovery, add, interval edit and delete.
- Exact activity, weight and BP deletion; signed hydration correction.
- Documentation and management skill route agents through schema, target,
  reviewed draft, at-most-once commit and operation-specific verification.

The native contracts and offline software checks are implemented. The new
mutations require separately scoped live acceptance before claiming account
acceptance. Real sleep edits can trigger recalculation, and main sleep lacks
normal deletion; implementation authorization is not permission for a synthetic
real-night test. Existing Lifestyle test authorization does not cover these
records. No new live mutation has been performed for this work.

## Deliberately unregistered research work

| Area | Gate before implementation/registration |
| --- | --- |
| Broader activity summary edits | Trace exact field/unit payloads and sport support. In particular pool-swim distance/time cannot use a generic summary patch. Preserve original file semantics and derived-field recalculation limits. Existing name/description/type writes remain. |
| Activity trim/restore and swim lengths | Establish native request/body, eligibility and restoration semantics. No generic raw sample editor or silent import replacement. |
| Targeted strength-set edits | Verify recorded-load units, stable set identity and partial-versus-complete replacement semantics. Existing full replacement preserves native raw units; never label them kg or infer conversion. |
| Calendar move | Define precise old calendar-entry identity, ordering and partial-failure reconciliation around existing schedule/unschedule operations. No atomic move claim or automatic rollback after unknown writes. |
| In-place weight/composition/BP edits | Verify actual update contracts. Creation/deletion do not establish an in-place editor. Do not disguise delete/recreate as update. |
| Device HR zones, sport-specific zones and detection thresholds | Read actual selected-device capabilities/settings first, then verify basis/units, ordered bounds and preservation of unrelated settings. Historical zone metrics are not the editable settings DTO. |
| Usual sleep schedule | Verify selected-device settings and sync semantics. It is separate from a dated sleep record and varies by device. |
| Training-status pause/resume | Verify account/device scope, current preference, enum/body and readback before registering a setter. Dated training status/load is not an arbitrary writable metric. |
| Personal-record accept/discard/assign | Native record/candidate/type routes exist, but route names alone do not establish business semantics, ownership, units or effect on record history. Require source-backed contract fixtures before enabled writes. |

For these areas the registry reports a boundary and, where useful, an
unregistered candidate. No endpoint/body passthrough is offered. Further
investigation can proceed without changing an account; live acceptance must
cover exact resources and intended side effects once a contract is concrete.

## Read capabilities without direct write counterparts

Sensor data and Garmin-derived HRV, stress, Body Battery, readiness, VO2 max,
thresholds, race predictions, sleep stages/scores and daily totals have no
verified direct setters. Correct eligible source records and recompute local
analysis instead. Coaching inputs/overrides retain their user provenance; they
do not overwrite Garmin scores. Catalogs and schemas are reference resources.
Archive/analysis functions operate on opted-in local storage, not Garmin records.

## Acceptance checklist for subsequent contracts

Trace native method/route, ownership, identity, unit and null semantics; retain
minimal derived notes. Add bounded target reads, strict schemas, stale guards,
policy/scope enforcement and durable replay tests. Test malformed data, correct
selection among same-day records, preservation of untouched data, upstream
uncertainty and readback mismatch. Add agent guidance and capability coverage.
Run foundation checks before authentication, then offline/package/CI gates;
keep expressly authorized live tests outside default tests and CI. Never claim
an unrun gate passed or a physical sync completed from queue acceptance.
