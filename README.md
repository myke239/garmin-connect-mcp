# Garmin Connect MCP

Local read-only Garmin Connect tools for Codex and other MCP clients. Python
3.12+; stdio transport; no listening port or background service. MIT licensed.
This uses the unofficial python-garminconnect library, not Garmin's partner API.

## Status

All six implementation phases have local verification evidence in PHASES.md.
Garmin login, independent saved-session restoration, activity/detail comparisons,
splits, samples, strength sets, summaries and actual MCP requests passed on this
machine. Codex's saved MCP command is registered and tested. Open a fresh Codex
chat or restart the app to load the new tools in the desktop conversation.

## Install

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\garmin-connect-mcp.exe login
.\.venv\Scripts\garmin-connect-mcp.exe verify
```

Python 3.12 also works. On this machine the tested environment is `.venv313`,
under `D:\developer\garmin-connect-mcp`. Runtime dependencies are pinned in
pyproject.toml; requirements-windows-py313.lock records the complete tested
Windows environment (not a cross-platform lock). CI never uses account credentials.

## Authentication

Enter your email, password and MFA code only at the local login prompts. On
Windows, session tokens are encrypted with current-user DPAPI and stored at
`D:\developer\.garmin-connect-mcp\session.dpapi`. Protected ACLs allow only your
Windows user and SYSTEM. `GARMIN_MCP_DATA_DIR` overrides the data directory. On
other platforms the default is ~/.local/share/garmin-connect-mcp, with owner-only
permissions. No plaintext token file is written on Windows.

`GARMINTOKENS` must be unset, preventing the upstream library's plaintext-store
fallback. Passwords are never saved. Tokens refresh during reads and are saved
encrypted. Windows' native certificate trust is used; TLS verification stays on.
Keep MFA enabled. Logout removes the local session and invalidates cached data;
it does not revoke a token already issued by Garmin.

On this machine:

```powershell
& 'D:\developer\garmin-connect-mcp\scripts\login.ps1'
```

## Connect Codex

### Install as a local plugin (recommended)

The Garmin Connect plugin bundles the seven read-only MCP tools and an
`analyze-training` skill. Source and the Python environment stay in this project;
Codex manages its installed plugin copy in its normal application cache.
Your encrypted Garmin session is shared with the existing server, never packaged.

After installing the Python environment above, run:

```powershell
& .\scripts\install_plugin.ps1
codex plugin list --marketplace myke-garmin --json
```

The installer resolves this checkout's interpreter and updates the plugin's local
MCP command, registers the private `myke-garmin` marketplace, and installs/enables
`garmin-connect`. Supply `-PythonPath` if your environment has another location.
This is a Windows local plugin; install and authenticate independently on each
machine. It does not provide web/mobile/cloud access or publish a public plugin.

Open a fresh chat or restart Codex after installation. Example: "Summarize my
running over the last four weeks." The skill can also be invoked explicitly as
`$garmin-connect:analyze-training` when loaded by the client.

If you previously registered a standalone server with the same name, remove it
after installing the plugin so that it does not override the plugin configuration:

```powershell
codex mcp remove garmin-connect
codex mcp list --json
```

To update after changing the source, rerun `scripts/install_plugin.ps1`. To
uninstall, use `codex plugin remove garmin-connect@myke-garmin`; this leaves your
source, Python environment and encrypted session intact.

### Standalone MCP alternative

```powershell
codex mcp add garmin-connect -- 'D:/developer/garmin-connect-mcp/.venv313/Scripts/python.exe' -m garmin_connect_mcp.cli serve
codex mcp get garmin-connect --json
```

Use your own absolute interpreter path on another computer. Set
`startup_timeout_sec = 30` and `tool_timeout_sec = 240` in the server's
`[mcp_servers.garmin-connect]` configuration table. There are no secrets in that
configuration. Open a fresh chat after registration.

Example request: "Pull my latest run and summarize my training for the last
seven days." Ask for date ranges explicitly when you need a particular timezone.

## Tools

A deferred future plan for direct GPT Actions is documented in
[gpt-actions/README.md](gpt-actions/README.md). Its schema validates, but Garmin
developer access is not available and GPT Actions PKCE compatibility is unverified. It
is not an installed or working ChatGPT mobile integration.

| Tool | Scope |
| --- | --- |
| connection_status | Local saved-session status; does not claim live verification |
| list_activities | Inclusive local date range, up to 90 days; 1–50 rows/page; next_cursor |
| get_activity | Distance, time, speed, pace, heart rate, elevation and calories |
| get_activity_splits | Up to 500 laps; explicit metric units |
| get_activity_samples | Heart rate only, up to 1,000 points; Unix-ms timestamps |
| get_strength_sets | Up to 500 sets; reps/exercises; Garmin raw weight with unverified units |
| get_training_summary | Up to 500 activities; complete/partial coverage and missing-metric counts |

GPS and raw upstream responses never appear in tools. Names and exercise labels
are explicitly marked as untrusted data, not instructions. Missing data remains
null or unavailable, never an invented zero. Sample data may be downsampled by
Garmin and locally; responses disclose this. Strength weights are deliberately
not labeled kg/lb until their upstream units can be verified.

## Reliability and privacy

Requests run in isolated subprocesses, with a 45-second per-attempt deadline.
Timeouts kill and wait for the worker. Only transient network/server failures get
one retry; auth failures, rate limits and client errors are not retried. Reads and
refreshes are serialized, including across server instances through a session
file lock. The in-memory cache holds at most 128 responses for 120 seconds,
labels cached results and invalidates on session-file changes. Summaries cap
pagination and report partial coverage if the deadline/page limit is reached.
Tool failures return bounded error codes without exception bodies or credentials.
stdout is exclusively the MCP protocol; logs go to stderr.

Only the seven read tools are exposed. No generic endpoint, upload, edit, delete,
workout scheduling or arbitrary file-export tool exists. The underlying Garmin
token can have broader privileges, so protect it like a password. Data returned
to Codex becomes part of the requesting conversation.

## Verification

Default tests are offline. Explicit live tests read your account but only print
check results:

```powershell
.\.venv313\Scripts\python.exe scripts/verify_live.py
.\.venv313\Scripts\python.exe scripts/verify_live.py --codex-config
```

A Windows-specific network framing issue required an ignored installer workaround
on this machine; it is not product code. Normal installation commands are used in
CI and on other computers. See PHASES.md for evidence and remaining limitations.
