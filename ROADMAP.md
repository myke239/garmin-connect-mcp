# Comparison implementation roadmap

Owner-authorized scope tracked in issue #20. Each phase requires a feature
branch, passing offline tests, bounded live tests where meaningful, a PR and
merge. Credentials, journals and private audit output are never published.

1. Recovery/context reads and higher-level running, strength/timed and swimming
   builders. Verify upstream shapes, units, missing data and exercise identity.
2. Optional local FIT archive, historical analytics, richer samples, interval
   comparison, and previewed template clone/rename/delete/existing-calendar batches.
3. Operation allowlists/tool profiles, stronger optional Linux secret storage,
   upstream catalog drift checks and safe credential migration.
4. Desktop setup UI, optional restartable service/startup, Docker and executable
   packaging, diagnostics, lint/type/build/secret/dependency CI gates.

Physical watch execution requires owner evidence after sync; server readback
must never claim animation/device execution verification. Official Garmin
developer OAuth and hosted multi-user operation remain outside this personal
connector: developer access and a separately reviewed tenant architecture are
prerequisites, not features an unofficial SDK can provide.

Phase 1 verification complete: 384 offline tests on WSL, 382 on Windows with
two platform skips, installed WSL protocol checks and live recovery/builder
readback plus synthetic cleanup. Publication is tracked by the phase PR.
Phases 2–4 remain in progress; this is not a claim that the roadmap is complete.

Phase 1 merged as PR #21. Phase 2 implemented: local FIT archive, richer samples,
interval comparison, power/drift analysis, clone/rename/delete and existing-workout
calendar batches. Live lifecycle and original-recording checks passed with cleanup.
