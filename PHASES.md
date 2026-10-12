# Verification record

## Version 0.3 — account-write audit

All 16 exposed write operations were exercised through the real SDK with an
intercepted transport and through authorized live test resources. Scheduling and
duplicate preflight rejection were verified with fresh calendar reads. Activity
edits, all three upload formats and health writes were read back; imports can
appear asynchronously. Known test records were cleaned up. Device queue success
does not prove physical download. See [WRITE_AUDIT.md](WRITE_AUDIT.md) for the
full matrix, failed variant, cleanup evidence and SDK-only operation exclusions.

## Phase 1 — passed
Windows / Python 3.13 / MCP 1.30.0: real subprocess initialization, tool discovery,
status call, unknown write-tool rejection and clean shutdown.

## Phase 2 — passed
DPAPI roundtrip and protected ACL tests; invalid/corrupt store checks; refreshed
session persistence. Live login created an encrypted session. An independent
process restored it and read Garmin successfully with native certificate trust.

## Phase 3 — passed
Validation, pagination, omitted coordinates, explicit units and missing metrics.
Live list/detail reads agreed for distance, duration and HR within one unit or
0.1% display precision. Strength filtering tested with Garmin parent/subtype.

## Phase 4 — passed
Samples resolve descriptor indices, bound results and omit coordinates. Missing
channels are unavailable. Splits reconcile with activity distance. Live heart-rate
and strength-set reads succeeded. Seven-day summary distance matches activities;
coverage was complete. Strength-weight units remain explicitly unverified.

## Phase 5 — passed
Actual subprocess termination on timeout; malformed worker-output rejection;
serialized concurrency; bounded transient retries; no auth/rate-limit retries;
cache limits/expiry/metadata/session invalidation; no exception-secret leakage.
A Windows multiprocessing startup stall under MCP was found in live testing and
fixed with a subprocess worker. This production launcher passes live checks.

## Phase 6 — passed at protocol/configuration level
Seven read-only tools registered in Codex. Fresh MCP connections launched with
Codex's saved command completed live run/detail/splits/samples/summary calls and
cache verification. Desktop chat tool loading needs a fresh chat/app restart;
that UI reload cannot be proved from the current conversation's old tool list.

## Final local checks
Offline test suite and installable wheel build pass. See GitHub CI for independent
Windows/Linux checks once publishing is authorized. Default tests and CI never
use Garmin credentials. Personal profiles, tokens and activity values are not
included in these records.
