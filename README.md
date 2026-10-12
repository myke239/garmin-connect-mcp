# Garmin Connect MCP

A local, read-only Garmin Connect integration for Codex and other MCP clients.

**Status:** Phase 1 passed. Phase 2 authentication implemented with six passing
offline tests; live login and saved-session verification pending. Activity tools
will be built after that gate passes.

## Local Garmin login

On this machine, run in your own PowerShell terminal:

```powershell
& 'D:\developer\garmin-connect-mcp\scripts\login.ps1'
```

Enter credentials and MFA only in the local prompts. Windows sessions are stored
at `D:\developer\.garmin-connect-mcp\session.dpapi`, encrypted with current-user
Windows DPAPI and protected by an ACL granting only the current user and SYSTEM.
No plaintext session file is written. `GARMIN_MCP_DATA_DIR` overrides the location.
The upstream `GARMINTOKENS` variable must be unset to prevent its plaintext-store
fallback. On non-Windows systems the store uses owner-only file permissions.

The script checks an actual Garmin read, then launches a second process to test
session restoration. `garmin-connect-mcp logout` removes only the local session;
it does not revoke tokens already issued by Garmin. Connection failures are
reported without exception details to avoid credential leakage.

## Development setup (Windows)

Requires Python 3.12 or newer. Run from this repository in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q
```

The development build targets the stable MCP SDK 1.x API. Dependency ranges are
declared in pyproject.toml; exact versions will be locked after installation and
successful testing. Do not treat this build as verified until the tests pass.

## Codex registration (after the test gate passes)

Use the absolute path to your virtual environment executable:

```powershell
codex mcp add garmin-connect -- 'C:\path\to\garmin-connect-mcp\.venv\Scripts\garmin-connect-mcp.exe'
codex mcp list
```

Restart or open a fresh Codex session if needed. The only current tool is
`connection_status`; it reports `auth_required` and does not contact Garmin.

## Development gates

1. Foundation: install and lock dependencies; pass subprocess initialization,
   tool discovery, read-only status call, rejection of an unknown write tool,
   and clean shutdown. No Garmin credentials needed.
2. Authentication: add interactive local login/MFA, Windows-restricted token
   storage outside the repository, restart/session restoration, and sanitized
   errors. Verify live sign-in before building activity retrieval.
3. Activities: normalize list/detail responses, validate arguments, cap pages,
   compare a real run with Garmin, and test missing fields and pagination.
4. Details: add splits, bounded samples, strength sets and summaries; compare
   representative activities and distinguish missing metrics from zero.
5. Reliability: enforce timeouts, serialized requests, bounded cache and retries;
   simulate rate limits, token expiration, malformed data and offline operation.
6. Codex integration: register locally and verify a fresh chat can retrieve the
   latest run and seven-day totals, including after restart.

Do not move past a gate that fails. Offline fixture tests are the default;
live tests must be explicitly invoked and never run in CI.

## Security design

No credential arguments or secrets in config/logs. stdout is for MCP only.
Authentication occurs through a separate local command in Phase 2. Token ACLs
must be enforced on Windows; POSIX chmod alone is insufficient. Tokens may grant
broader Garmin account access even though the tool surface is read-only.
GPS coordinates will be omitted by default. No arbitrary endpoint proxy will be
exposed. Activity titles and notes are data, not instructions for the client.

## Repository publication

After signing in with `gh auth login --hostname github.com --web`, configure
your Git author if needed, commit the files, and create a private repository:

```powershell
git add .
git commit -m 'Add local MCP foundation and phased test plan'
gh repo create garmin-connect-mcp --private --source . --remote origin --push
```

Review `git status` before committing. Tokens, .env files and the virtual
environment are ignored. This repository has no license yet; select one before
public redistribution.

