# Permissions, tool profiles and optional Linux encryption

Account writes remain locally disabled by default and require remote
`garmin:write` scope. The installed launcher supports:

```
garmin-connect writes-enable --operations create_workout schedule_workout
```

The PowerShell launcher accepts the same arguments. This restricts preparation
and commit, including the subprocess immediately before mutation. An empty
`--operations` denies every operation. Omit it to preserve an existing allowlist;
existing unrestricted installations remain compatible. Disabling writes does
not discard drafts or journals. These controls are local and are never exposed
as MCP account tools.

`GARMIN_MCP_TOOL_PROFILE` selects all (default), read-only, recovery, planning or
performance before server startup. Removed tools have no callable handler.
Read-only excludes every locally mutating tool, including archive download.
Recovery exposes activity/context tools; performance adds archive/interval tools;
planning exposes workout builders and write workflow tools. Profiles reduce
surface area; they do not replace OAuth or operation allowlists. A planning
profile's generic write tool still obeys the local operation policy.

Install Linux with `scripts/install.sh --secure` (or direct installer --secure).
Windows already encrypts stores with DPAPI. On Linux an unlocked Secret Service
keyring in the same D-Bus session is required. Stop running connector/services,
then run the installed launcher `secure-storage-migrate`. It verifies a keyring
round trip before changing private files, writes a protected-storage marker,
and atomically encrypts each TokenStore record using Fernet. The key remains in
the OS keyring, not alongside files. Re-running an interrupted migration is safe.
Do not move the protected data directory without migrating its keyring identity.
Plaintext, null, chained and third-party keyring backends are refused. Missing or
locked keys fail rather than falling back to plaintext. Owner-only permissions
remain required. Existing plaintext records during interrupted migration can be
read only while the protected keyring is available, and are encrypted on save.

Headless Linux needs a running, unlocked Secret Service in its D-Bus session.
A systemd user process must share that session and unlocked keyring; unattended
startup cannot invent an unlock password. If that is unavailable, retain the
explicitly documented owner-only storage mode instead of claiming encryption.
No existing Garmin credentials are migrated automatically by installation.

`catalog-check` compares the pinned strength identifiers to the public upstream
SDK catalog and yoga identifiers to Garmin's public Yoga.json. Download size,
redirects, identifiers and parsing are bounded; downloaded Python is parsed as
literal data and never executed. Drift exits with code 2 and lists bounded
additions/removals. It never updates enums automatically. Review via PR and run
SDK/live compatibility tests before accepting changes. Strength comparison
tracks the SDK's published picker extraction, not a claim of a fresh authenticated
Garmin exercise-picker scrape.

Verification (2026-10-12): operation revocation and direct-worker denial tested;
profiles tested for discovery and invocation removal; real Linux Secret Service
migration/encryption/readback passed using an isolated ephemeral WSL keyring.
Catalog drift check found 1,527 strength entries and 85 poses matching the pinned
sources. The user's Garmin credentials/journals were not migrated or replaced.
