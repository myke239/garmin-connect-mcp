# Per-user installation

Version 0.8.1 adds command-line installers and standalone launch commands.
This is the first installation stage: managed Python, no manual environment
activation, and no working-directory dependency. A graphical installer/tray app
or frozen executable is not included.

## Standard locations

| Platform | Application/runtime default | Launcher |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\Programs\GarminConnectMCP` | `bin\garmin-connect.ps1` |
| Linux | `${XDG_DATA_HOME:-~/.local/share}/garmin-connect-mcp/application` | `bin/garmin-connect` |

No administrator/root access, system Python replacement, PATH changes or startup
service is required. Source stays in the checkout. Managed Python, dependency
environments and caches stay under the installation directory. Each installation
gets a new release directory; its launcher is published only after package
installation and an offline MCP discovery check succeed. An installation failure
before publication leaves the previous launcher intact. Old release directories
are retained, including environments potentially used by an active connection.
Reinstalling is not an automatic restart or plugin refresh.

Credentials and write journals remain separate. Existing Windows installations
using `D:\developer\.garmin-connect-mcp` keep that location; new Windows users
use `%LOCALAPPDATA%\garmin-connect-mcp`. Linux retains
`~/.local/share/garmin-connect-mcp`, honoring an absolute `XDG_DATA_HOME`.
`GARMIN_MCP_DATA_DIR` overrides this on either platform. Do not point Windows and
Linux at the same session: Windows DPAPI files are not Linux tokens. Linux
sessions are owner-only plaintext files, not encrypted by this application.

## Windows

From an existing trusted checkout, run this from **any directory**:
```powershell
& 'D:\developer\garmin-connect-mcp\scripts\install.ps1'
$Garmin = Join-Path $env:LOCALAPPDATA 'Programs\GarminConnectMCP\bin\garmin-connect.ps1'
& $Garmin doctor
& $Garmin login
& $Garmin verify
& $Garmin install-plugin
```

Change the first path to your checkout. The installer uses an existing `uv` on
PATH or downloads Astral's official HTTPS installer into the application
directory, then obtains Python 3.13 and pinned runtime dependencies.
No credentials are requested during installation; login requires your terminal.
If local PowerShell policy blocks an unsigned script, invoke it using
`powershell -NoProfile -ExecutionPolicy Bypass -File '<absolute script path>'`
for that process only, where your organization permits it.

Use `-InstallDir 'D:\apps\GarminConnectMCP'` to override the application location.
Add `-Remote` to install phone/tunnel dependencies.

## Linux and WSL

Requires `sh`, `curl`, CA certificates and outbound HTTPS to Astral, GitHub and
the Python package index. A preinstalled Python is unnecessary.
```sh
sh /absolute/path/to/garmin-connect-mcp/scripts/install.sh
garmin="${XDG_DATA_HOME:-$HOME/.local/share}/garmin-connect-mcp/application/bin/garmin-connect"
"$garmin" doctor
"$garmin" login
"$garmin" verify
"$garmin" install-plugin
```

For this machine's WSL checkout the first path is
`/mnt/d/developer/garmin-connect-mcp/scripts/install.sh`.
Install Codex CLI **inside Linux** before Linux plugin registration.
WSL and Windows Codex installations are separate; Windows Codex should use the
Windows launcher, not a WSL registration.

Set `GARMIN_INSTALL_DIR=/absolute/custom/path` for an alternate application
directory. Use `--remote` for optional tunnel dependencies. Linux downloads
Astral's official installer only if `uv` is missing and never modifies PATH.

## Launch and authenticate

Append one of these commands to the full launcher path:
- `login`, `verify`, `logout`: Garmin authentication.
- `writes-status`, `writes-enable`, `writes-disable`: explicit local write settings.
- `serve`: MCP stdio (stdout belongs to the protocol).
- `doctor`: offline version, install, session-presence and optional-dependency
  checks; never displays token content or queries your account.
- `install-plugin`: register the isolated installed marketplace with Codex.
- `approve <ticket>`: review the existing local OAuth consent flow.
- `tunnel-setup`, `tunnel`, `tunnel-status`: optional phone connection.

For other MCP clients, use the absolute Python command recorded in the
installation's `installation.json` with arguments
`-m garmin_connect_mcp.cli serve`. Plugin registration uses that same interpreter
and copies manifests/skills into the installed release; it does not rewrite the
source checkout's `.mcp.json`.

For phone access, run the installer with remote extras, then `tunnel-setup` and
`tunnel`. Follow [REMOTE.md](REMOTE.md) for ChatGPT connection and consent.
Keep the PC awake and service running. Writes remain disabled until explicitly
enabled locally; installation never grants writes or approves OAuth.

## Update, remove and troubleshooting

Re-run the installer from the desired reviewed release, then `install-plugin`
to refresh local tools/skills. Registration replaces only the known one-plugin
`myke-garmin` marketplace and restores its previous source if the switch fails.
Unexpected additional plugins stop migration before removal. Restart your tunnel deliberately after checking
which runtime owns it. Open a fresh Codex chat. Preserve credentials and journals.
There is no automatic update, daemon installation, uninstall or cache cleanup.

Remove Codex registration with
`codex plugin remove garmin-connect@myke-garmin`. After stopping services, application
files can be removed separately; keep the data directory unless intentionally
revoking/removing local sessions. Failed installation release directories are
retained for diagnosis and can be removed once verified unused.

If `doctor` reports no session, login in the environment you intend to run.
If plugin registration reports missing Codex, put the Codex CLI on that platform's
PATH. TLS failures must be resolved with trusted CA configuration or narrowly
scoped antivirus exceptions; TLS verification is never disabled.

## Verification for 0.8.1

Windows and Ubuntu 22.04 under WSL2 installed successfully using uv 0.13.0
and managed Python 3.13.16. Launchers worked outside the checkout. Both
installed runtimes passed real MCP handshakes, discovery of 30 tools, local
write-schema lookup and unauthenticated HTTP rejection. Windows verified the
existing saved Garmin session. Linux was tested without account credentials;
its full offline suite passed 369 tests (Windows: 367 passed, two Linux-only
tests skipped). No account writes were performed for installation testing.

To repeat installed protocol checks with synthetic temporary state, run the
installed Python from its receipt against `scripts/verify_install.py` and
pass the absolute path to `installation.json`. CI performs isolated installs
on Windows/Linux and tests Python 3.12/3.13.
