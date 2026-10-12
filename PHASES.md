# Verification record

## Phase 1 — passed

Windows, Python 3.13, MCP SDK 1.30.0. Two tests passed: adapter injection and
actual stdio subprocess initialization, discovery, tool call, unknown-write-tool
rejection, and shutdown. No Garmin credentials or network calls used.

## Phase 2 — live gate pending

Six total tests passed after adding DPAPI roundtrip and protected ACL checks,
refreshed-token persistence, corrupted-token rejection, and invalid JSON not
replacing an existing session. Library pinned to garminconnect 0.3.17 with
curl_cffi 0.16.3. Interactive login and independent restore check are ready.

Required next evidence: user completes scripts/login.ps1 locally, then the
saved-session verification succeeds. Never record credentials, tokens, account
profiles or activity payloads in this file.

## Phases 3–6 — not advanced

Activity retrieval, workout details, reliability, and Codex live integration
depend on the Phase 2 live gate. See README.md for their test criteria.

## Machine setup note

Normal pip downloads on this machine received malformed HTTP chunk framing.
An ignored work-directory installer used a process-local HTTPS transport
workaround with certificate verification retained. This workaround is not part
of the product or the committed repository. The fresh development environment
is .venv313; the old relocated .venv is unused.
