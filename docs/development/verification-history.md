# Verification history

[Documentation home](../README.md)

## Structured workout authoring — 2026-10-27 (local evidence)

All 15 MCP foundation/runtime checks passed without Garmin authentication.
The complete Windows/Python 3.13 offline suite passed 673 tests, 9 skipped.
Acceptance cases independently expand repeat groups to check executing rests,
transition replacement, final-exercise behavior, 10 × 20s/40s practice, the
54-minute tempo example, SDK running/swim pace units, catalog resolution, nested validation,
larger bounded payloads, and synthetic update/readback/calendar identity.
MCP discovery exposes the enhanced builder defaults without adding a write path.

Documentation links and the 58-tool inventory, skill validation, source lint,
scoped strict typing, secret checks and source/wheel builds passed locally.
Research sources are recorded in the workout skill. This is offline structural
and synthetic transport evidence: no new live-account mutation, physical watch
execution, sync, installed deployment or release acceptance is claimed. PR CI
and merge are separate gates and must pass before merging.

## Namespaced HTTPS and release experience - 0.19.0 (2026-10-22, local evidence)

The 15 foundation/runtime checks passed before account verification. The complete
Windows offline suite passed 611 tests, 3 skipped. Namespaced HTTP tests exercise
PKCE, DCR, local-consent routing, metadata/issuer/resource identity, refresh,
revocation, both directions of token isolation, real 58-tool discovery, request
bounds, the canonical slash redirect, legacy saved-state compatibility and fresh
installations leaving root routes unclaimed. No real account mutation is involved.

An isolated installed 0.19.0 candidate passed a real MCP handshake, schema checks
and its namespaced HTTP 401 guard. Source lint, selected strict typing, document
links/inventory and source/wheel builds passed. Desktop construction passed;
two actual isolated Windows setup screenshots were captured without account data.
Dependency audit exposed old Pillow/certifi advisories; Pillow 13.0.0 and the
certifi 2026.10.19 floor replace them. The updated local dependency audit reports
no known vulnerabilities (the local non-PyPI project is explicitly unaudited).

The companion MyFitnessPal gateway's complete offline suite passed 113 tests,
including the new Garmin path and request bound. Its independently published
0.5.2 release at d4b3458 already includes the compatible gateway. CI, merged
release, packaged binaries and active deployment are separate subsequent gates;
no completion of those gates is claimed in this local evidence entry.

## Windows cross-process lock fix - 0.18.1 (2026-10-18, local evidence)

Active-deployment read checks exposed a PermissionError when one process read
request.lock's byte while another process held a Windows byte-range lock.
The old implementation was reproduced against a real held lock in an isolated
no-account directory. Moving initialization/read after acquisition passed a
real two-process contention/handoff test, including an empty new lock file.
The existing timeout and mutation journal semantics are unchanged.

15 foundation/runtime checks passed before any saved-session checks of this
patch. The full Windows offline suite passed 609 tests, 3 skipped. Documentation
inventory (58 tools), source lint, selected typing and secret checks passed.
Installed/live/CI/merge/deployment gates are separate and are not claimed here
before execution. No health record mutation is part of this regression test.

## Sleep and correction contracts - 0.18.0 (2026-10-18, local evidence)

14 MCP foundation/runtime tests passed before saved-account reads. Derived
Garmin Android 5.30.1 contracts established sleep/nap routes, native copy/default
DTO behavior, GMT strings, offset minutes and exact weight deletion. Pinned
SDK contracts supplied signed hydration and exact BP/activity deletion routes.
Saved-account GETs confirmed the current sleep DTO and weight day-view shapes;
BP discovery on an empty date does not validate a nonempty account response.
No app binary, decompiled source or personal response is committed.

Windows offline suite: 608 passed, 3 skipped. New cases cover exact registry
coverage, policy/profile/grant reporting, snapshot bounds, main-sleep absence
versus overwrite, DST offsets, native metadata preservation, current-day nap
identity/overlap/midnight, exact same-day deletion, signed ml bounds/nonnegative
totals, readback mismatch, terminal uncertain outcomes and commit replay.
Source lint, selected strict typing, documentation links/inventory (58 tools),
management-skill validation, source/wheel build and third-party dependency audit
passed. The local editable project itself is skipped by the public-PyPI audit.

An isolated Windows candidate passed installed MCP discovery (58 tools), offline
schema and HTTP authentication guard checks. Its real MCP transport passed all
37 operation schemas and saved-account read-only sleep/nap/weight/BP target
calls. A live hydration read exposed an unset/null total; the target now reports
correction unavailable without replacing null with zero, with regression tests. No new live mutation acceptance is claimed: real-night changes need exact
scope authorization; main-sleep creation cannot normally be cleaned up. Device
settings, PR semantics and other unverified corrections remain unregistered as
listed in [write coverage](write-coverage.md). CI, merge and active deployment
are separate gates; no pass is claimed before those checks run.

## Lifestyle write contracts - 0.17.0 (2026-10-16, local evidence)

14 foundation/runtime tests passed before saved-session reads. Garmin Connect
Android 5.30.1 (11657), copied from the owner's authorized connected phone,
provided fixed endpoint, HTTP method, enum and DTO evidence. No APK or decompiled
source is committed. A saved-session GET verified 47 dated catalog definitions
and the nullable global auto-logging preference without storing personal values.

Windows offline suite: 546 passed, 3 skipped. The 51 new synthetic cases cover
all seven operations, actual transport method/body interfaces, stale catalog and
log evidence, native subtype IDs, integer zero/NO/clear distinctions, immutable
built-ins, duplicates, local operation policy, terminal unknown outcomes,
idempotent journal replay, readback mismatch, privacy projection and MCP schemas. Additional cases cover unset versus explicit-false preference
and native Lifestyle mutation replay blocking after a 401. Source MCP discovery
and live read-only catalog/preference calls passed.
Documentation inventory exposes 54 tools. Source lint, documentation/secret
checks, management-skill validation, selected strict typing and wheel/source
build passed. These are software/contract checks, not live mutation acceptance.
An isolated Windows installed candidate passed the real MCP handshake (54 tools),
offline schemas, HTTP 401 guard and saved-session catalog/preference reads.
The initial pip install failed due to a broken package transfer; the standard uv
installation completed successfully. Live account writes, active deployment and
CI are separate gates; no pass is claimed before those checks run.

### Authorized live Lifestyle acceptance (2026-10-16)

Through real MCP prepare/commit and fresh reads: two explicitly approved synthetic
custom definitions were created, added to tracking, logged, renamed and deleted.
Positive quantities 1 and 2, quantity NO, yes/no YES/NO, daily clear, custom rename,
tracking restoration and batch definition deletion passed readback. Repeated
commits returned their journal results without repeating account mutations.
Original tracked-ID membership was restored and both test IDs were absent from
the final catalog. Medication and other existing logs were not edited.

A zero-quantity request failed upstream; fresh readback retained the prior
quantity 2. The uncertain journal result was preserved, inspected and not retried.
Zero writes are now rejected locally (positive amounts only), with regression
coverage. Read zeros remain unchanged; NO/clear are never substituted implicitly.
Global auto-logging writes were not tested because the owner's unset preference
could not be restored by a verified reset operation. Historical erasure and
physical watch sync are not claimed. CI must pass on this corrected patch before
merge and deployment.

## Coaching discovery acceptance — 0.16.1 (2026-10-16, local evidence)

495 offline tests passed, 3 skipped. New acceptance scenarios execute the guide's
four synthetic examples through MCP and independently verify nonconstant
percentiles, lifestyle lag direction, strength-window boundaries, equipment
separation, historical-reference ranges and malformed nested inputs. The guide
provides current schemas, units and limits without account access. Documentation
and skill updates address input discovery, not clinical or prospective model
validation. Installed-runtime and live deployment checks are separate gates.

## Strength-first coaching foundation — 0.16.0 (2026-10-16, local evidence)

14 MCP foundation/runtime tests passed before account reads. Windows offline
suite: 489 passed, 3 skipped. New synthetic tests cover baseline exclusion,
missing/zero, source/date/timezone alignment, finite values and units, typed MCP
transport, nutrition projection, future-outcome rejection, exploratory lag
matching, strength region overlap, warmups, unknown load/RIR and exercise order.
Documentation inventory (51 tools), secret checks, source lint, selected strict
typing checks, both skill validators and wheel/source builds passed.

Read-only live checks verified two dated Garmin coaching days and MFP diary
keys/completion type. A combined in-memory projection passed without printing or
storing personal quantities in artifacts. Readiness without confirmed morning
context was excluded. These are source/contract checks, not prediction accuracy.
No account writes, coaching archive, automation changes or deployment were made.
Strength prediction, clinical validity and prospective evaluation remain open;
see [research gates](coaching-research.md). CI must pass on the feature PR before merge.

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

## Version 0.20.1 — setup URL regression (2026-10-23)

The new graphical regression test reproduced the blank URL before the fix and
passed afterward, checking both the read-only entry and clipboard after garbage
collection. All five wizard tests passed; the full offline suite passed with
637 tests and 9 skips. Graphical tests share one Tcl interpreter, matching the
application's lifecycle. Documentation checks, lint and scoped strict typing
passed locally. Azure signing remains unverified until the owner's validated
account/profile and federated identity configuration are available.

## Version 0.20.0 — guided installation (2026-10-23)

Local Windows/Python 3.13: foundation checks passed (15); complete offline suite
passed (636 passed, 9 skipped). Wizard tests exercised failed sign-in without
secret leakage, synthetic MFA, Codex completion, shared-host navigation and exact
request approval. OAuth transport tests preserved other pending requests and
rejected changed scopes, expired requests and preexisting requests.

Frozen MCP discovery exposed all 58 tools and passed guarded lifecycle checks.
The production unsigned installer passed isolated per-user installation, launch,
vendor metadata and uninstall with private-data preservation. A genuine installer
welcome screenshot is included in the short guide. Lint, strict typing of the
typed launch/diagnostics modules, documentation links, source/wheel build and
dependency audit passed locally. No Garmin login, MFA or health writes were
performed against a live account. CI results are recorded on the release PR;
local checks do not substitute for independent platform gates.

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
