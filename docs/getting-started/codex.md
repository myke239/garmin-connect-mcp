# Connect Codex and other MCP clients

[Documentation home](../README.md) · [Install first](installation.md)

## Codex plugin

On Windows, select **Codex** in the setup wizard, then **Connect Codex**.
Setup obtains the official helper if needed. Open a new Codex chat after success.

### Terminal setup

After installation, invoke the full installed launcher with `install-plugin`:

```powershell
$Garmin = Join-Path $env:LOCALAPPDATA 'Programs\GarminConnectMCP\bin\garmin-connect.ps1'
& $Garmin verify
& $Garmin install-plugin
```

```sh
garmin="${XDG_DATA_HOME:-$HOME/.local/share}/garmin-connect-mcp/application/bin/garmin-connect"
"$garmin" verify
"$garmin" install-plugin
```

The Codex CLI must be on PATH in that OS. WSL and Windows have separate Codex installations. Registration adds the project's one-plugin `myke-garmin` marketplace and installs `garmin-connect@myke-garmin`. Open a **new Codex chat** to load updated tools/skills. Start with “Use Garmin Connect to summarize my last three runs.”

The installer copies manifests and skills into an isolated release and writes an absolute runtime command into the installed configuration. The checkout's `.mcp.json` remains unchanged. Replacing a marketplace with unexpected additional plugins is refused; failed replacement restores the known prior source.

## What the local skills provide

| Skill | Purpose |
| --- | --- |
| `analyze-training` | Read sessions, recovery, intervals and optional archives with units/coverage respected. |
| `daily-performance-coach` | Strength-first daily physiology, nutrition and exercise-exposure evidence. |
| `review-training-recovery` | Multiweek recovery, matched outcomes and exploratory lifestyle patterns. |
| `browse-garmin-exercises` | Search exact strength/pose identifiers and paginate without substitutions. |
| `create-schedule-workouts` | Discover schemas, build, prepare, review, commit and verify templates/calendar entries. |
| `manage-garmin-account` | Follow contracts for activities, measurements, imports and device delivery. |

The plugin contains no credentials or activity history. Login/session protection remains in the server. These skill files load in Codex; ChatGPT HTTPS clients instead receive tool descriptions and queryable schemas/contracts. See [workout workflow](../guides/workouts.md).

## Other MCP clients

Use the absolute interpreter from the installed `installation.json`:

```json
{
  "mcpServers": {
    "garmin-connect": {
      "command": "/absolute/path/from/installation.json/python",
      "args": ["-m", "garmin_connect_mcp.manage", "serve"]
    }
  }
}
```

Replace the placeholder with the actual OS path; JSON Windows paths need escaped backslashes. For an executable installation, use its absolute `garmin-connect.exe` (Windows) or `garmin-connect` (Linux) with `args: ["serve"]`. Do not use a PowerShell script as an executable command unless your client explicitly supports that shell invocation.

For standalone Codex MCP registration, the equivalent is:

```text
codex mcp add garmin-connect -- /absolute/path/to/python -m garmin_connect_mcp.manage serve
```

Configure a 30-second startup timeout and a 240-second tool timeout if the client supports them. Keep stdout reserved for MCP. Avoid registering both the plugin and a separate MCP entry with the same server, which can duplicate tools.

## Updates and removal

Re-run the installer from reviewed source, then `install-plugin`. A running remote service needs an intentional restart; preserve private grants and journals. Refresh ChatGPT tool definitions separately where needed. Default discovery is 58 tools; smaller [profiles](../guides/permissions-and-storage.md) intentionally expose fewer.

Remove registration with `codex plugin remove garmin-connect@myke-garmin`. That does not erase your Garmin session or stop an HTTPS process. Stop the service separately and use local logout/remote reset if you intend to revoke access.

Developers can still use `scripts/install_plugin.ps1` from a tested development checkout. It regenerates that checkout's machine-specific interpreter path; do not commit the generated path. See [CONTRIBUTING](../../CONTRIBUTING) and [verification history](../development/verification-history.md).
