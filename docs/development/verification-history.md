# Verification history

[Documentation home](../README.md)

## Lifestyle reads — 0.15.0 (2026-10-14, local evidence)

14 foundation/runtime tests passed before saved-session live Lifestyle reads.
The complete Windows offline suite passed 457 tests with 3 skips; source lint,
documentation inventory (46 tools), secret checks, wheel and source build passed.
Live custom-field discovery and seven-day raw-amount agreement passed; the oldest
date of a 90-day window was readable. Synthetic tests cover full 90-day pagination,
zero versus missing, filtering, bounds, unsupported shapes and error propagation.
No Lifestyle writes were performed. Complete catalog discovery, stable entry IDs,
entry CRUD and custom definition management remain unverified. CI is separate
evidence and must pass on the feature PR before merge.

## Current release — 0.12.0 (2026-10-12)

All four software phases merged through PRs #21–#24. Windows and WSL installed-runtime MCP discovery exposed 44 default tools and unauthenticated HTTP returned 401. The Windows saved Garmin session verified; the public endpoint returned 401 and OAuth metadata advertised read/write scopes. The final WSL suite passed 419 tests. Windows/Linux Python, installation, executable, container and quality CI jobs passed.

Watch execution and macOS/ARM executable support remain unverified. Dated prior gates below are historical evidence, not current tool/test counts.

## Installation release — 0.8.1 (2026-10-12)

Per-user Windows/Linux setup, isolated release environments, absolute launchers
and offline installation diagnostics. Graphical/tray UI remains future work.
See [installation](../getting-started/installation.md) for usage and platform limitations.

# Verification record

## Current release — 0.8.0 (2026-10-12)

357 offline tests passed locally; independent Windows/Linux CI passed on PR #16.
Installed plugin skills matched merged source, and live MCP discovery exposed
30 tools. Authenticated public reads and read/write scope separation passed.
All four operation-specific workout commits passed isolated live tests; temporary
templates and calendar entries were removed and verified. The owner subsequently
reported the blocked ChatGPT workflow working. This report is limited to one
case and does not establish a universal OpenAI safety-block resolution.

The phase records below describe historical verification, not current tool counts.

## Version 0.3 — account-write audit

All 16 exposed write operations were exercised through the real SDK with an
intercepted transport and through authorized live test resources. Scheduling and
duplicate preflight rejection were verified with fresh calendar reads. Activity
edits, all three upload formats and health writes were read back; imports can
appear asynchronously. Known test records were cleaned up. Device queue success
does not prove physical download. See [write audit](write-audit.md) for the
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
Windows/Linux checks for each reviewed pull request. Default tests and CI never
use Garmin credentials. Personal profiles, tokens and activity values are not
included in these records.

## Comparison roadmap (2026-10-12)

See [roadmap](roadmap.md) and phase PRs #21–#24 for recovery/builders, archive/
analytics/lifecycle and permissions/protected-storage verification. The deployment
phase adds actual executable, desktop and Docker protocol gates. Default CI stays
offline with respect to Garmin and never uses account credentials. Physical watch
execution remains unverified; server readback and queued sync cannot prove it.
