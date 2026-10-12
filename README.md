# Garmin Connect MCP

Read Garmin running and workout stats from Codex and other MCP clients, or
ChatGPT through an optional authenticated HTTPS tunnel. Read tools plus optional
previewed account writes; no arbitrary endpoints. An independent, unofficial project
built on [python-garminconnect](https://github.com/cyberjunky/python-garminconnect).

Version **0.3.1** · Python **3.12+** · **MIT** license.
The owner verified local Codex access and ChatGPT access on a phone. Your
ChatGPT account must support custom MCP plugins; account, workspace and mobile
availability can vary. This is installable source, not an approved public
ChatGPT marketplace listing or a hosted multi-user service.

## Install

Windows PowerShell:

```powershell
git clone https://github.com/myke239/garmin-connect-mcp.git
cd garmin-connect-mcp
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m garmin_connect_mcp.cli login
.\.venv\Scripts\python.exe -m garmin_connect_mcp.cli verify
```

Linux/macOS (local stdio):

```sh
git clone https://github.com/myke239/garmin-connect-mcp.git
cd garmin-connect-mcp
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m pytest -q
.venv/bin/python -m garmin_connect_mcp.cli login
.venv/bin/python -m garmin_connect_mcp.cli verify
```

Enter email, password and MFA only in local prompts. Passwords are not saved.
Unset `GARMINTOKENS` to avoid the SDK's plaintext-store fallback. Keep MFA enabled.
Runtime dependencies are pinned in pyproject.toml. The Windows lock records one
verified environment, not a cross-platform lock.

## Connect Codex

On Windows, install the local plugin after creating the Python environment:

```powershell
.\scripts\install_plugin.ps1
```

The installer resolves your interpreter and registers the `myke-garmin` local
marketplace. Open a new Codex chat. See [PLUGIN.md](PLUGIN.md) for verification,
updates and uninstalling. Installation changes the local `.mcp.json`; do not
commit your machine's generated interpreter path.

Alternatively use your own absolute interpreter path for standalone stdio:

```text
codex mcp add garmin-connect -- /absolute/path/to/python -m garmin_connect_mcp.cli serve
```

Other MCP clients can use the same command and arguments. Configure a 30-second
startup timeout and a 240-second tool timeout if supported. Example request:
“Use Garmin Connect to summarize my last three runs.”

## Connect ChatGPT and a phone

Follow [REMOTE.md](REMOTE.md) to install remote extras, save your ngrok token
locally, start the tunnel and create a ChatGPT custom MCP plugin with OAuth
and DCR. Consent requires approval in your local terminal. Test a new chat on
the web, then your phone. Your PC must remain awake, online and running the
tunnel. No automatic startup task is installed.

## Tools

Account writes are disabled by default. See [WRITES.md](WRITES.md) for enabling,
ChatGPT reauthorization, operations, parameters and limits. Use
`prepare_garmin_write` then `commit_garmin_write`; review before committing.
First query `get_garmin_write_schema` for exact names, types and units. New
verification tools read fresh schedules, devices, activity types, complete
strength-edit payloads and measurements. The plugin includes workout and
account-management skills. See [WRITE_AUDIT.md](WRITE_AUDIT.md) for tested paths,
cleanup evidence and limitations; all 16 exposed operations were tested live.
Existing remote grants remain read-only.

| Tool | What it returns |
| --- | --- |
| connection_status | Saved-session status, without claiming live verification |
| list_activities | Inclusive local date range up to 90 days; 1–50 rows/page |
| get_activity | Distance, duration, speed, pace, heart rate, elevation, calories |
| get_activity_splits | Up to 500 laps, explicit metric units |
| get_activity_samples | Up to 1,000 heart-rate samples, Unix-ms timestamps |
| get_strength_sets | Up to 500 sets; raw weight units remain unverified |
| get_training_summary | Up to 500 activities with complete/partial coverage |
| list_workout_templates | Up to 50 workout IDs, names and sports |
| get_workout_template | Full template structure for previewed edits |
| prepare_garmin_write | Persist a validated draft; no Garmin mutation |
| commit_garmin_write | Apply the reviewed draft; write permission required |
| get_garmin_write_schema | Exact operation contract, bounds, units and guidance |
| get_garmin_write_status | Durable outcome without committing or retrying |
| list_scheduled_workouts | Fresh calendar entries and IDs for one month |
| list_garmin_devices | Explicit device IDs for queued workout delivery |
| list_garmin_activity_types | Valid type ID/key/parent tuples |
| find_garmin_exercises | Pinned SDK exercise category/name catalog |
| get_activity_edit_template | Complete strength payload and editable activity fields |
| get_garmin_measurements | Fresh measurements for one calendar day |

Missing values remain unavailable. Names and exercise labels are untrusted data,
not instructions. Samples may be downsampled; responses disclose this. Activity
reads omit GPS. Uploaded activity files can contain GPS and are opt-in writes.

## Privacy and reliability

Windows sessions use user-bound DPAPI encryption and user/SYSTEM-only ACLs.
New installations default to `%LOCALAPPDATA%\garmin-connect-mcp`; existing
installations with `D:\developer\.garmin-connect-mcp` retain that directory.
Set `GARMIN_MCP_DATA_DIR` for an explicit private location. Linux/macOS use
`~/.local/share/garmin-connect-mcp` with owner-only permissions; the application
does not encrypt tokens there. Remote setup is tested on Windows.

Protect session files like passwords: the underlying Garmin grant can have
broader privileges than the tools. Logout deletes the local session, not
Garmin-issued tokens remotely. Assistant tool results enter the conversation.
Ngrok carries remote tool responses; review its terms and privacy policy.

Reads use isolated subprocesses, deadlines, one retry for transient errors,
shared session locks and a bounded short-lived cache. Auth failures and rate
limits are not retried. TLS verification stays enabled. Protocol stdout is
reserved for MCP. Remote OAuth grants are separate and locally revocable.

## Development and verification

Default tests and Windows/Ubuntu CI are offline. Live checks are explicit:

```text
python -m pytest -q
python scripts/verify_live.py
```

Historical phase gates and verification are in [PHASES.md](PHASES.md). Verify
protocol and offline checks before Garmin login, then explicit live reads, then
client integration. Never claim a phase passed without checking it.
A deferred partner API experiment is in [gpt-actions/README.md](gpt-actions/README.md);
it is separate from the working HTTPS mobile connection.

See [CHANGELOG](CHANGELOG), [VERSION](VERSION), [LICENSE](LICENSE),
[CONTRIBUTING](CONTRIBUTING) and [NOTICE](NOTICE). Report reproducible problems
through [GitHub issues](https://github.com/myke239/garmin-connect-mcp/issues)
with synthetic data and redacted logs.
