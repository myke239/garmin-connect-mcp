# Per-user installation

[Documentation home](../README.md)

Version 0.16.1 includes managed installers, a desktop setup/tray application,
optional per-user background startup and downloadable frozen builds. Every
launcher works from any directory with no environment activation.

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
sessions default to owner-only files. Optional Secret Service encryption and
migration are described in [permissions and storage](../guides/permissions-and-storage.md).

## Choose an installation

| Route | Choose it when | Prerequisites |
| --- | --- | --- |
| [Executable bundle](#executables-and-desktop-setup) | You want desktop setup or a CLI without installing Python for core tools. | Windows x64 or Linux x86-64/glibc 2.35+; keep the entire extracted bundle together. |
| Managed source installer ([Windows](#windows) / [Linux](#linux-and-wsl)) | You prefer a reviewed Git checkout and automatic Python/dependency setup. | Git (or an extracted source checkout), outbound HTTPS; Linux also needs curl/CA certificates. |
| Development environment | You are changing or testing the server. | Python 3.12+; see [CONTRIBUTING](../../CONTRIBUTING). |
| [Local Docker build](#build-executables-and-use-docker) | You prefer an isolated Linux runtime. | Docker; separate Linux credentials and a private data volume. |

The install commands below start with a fresh public checkout. To work from another directory later, use the absolute installed launcher. You can choose a different source checkout path.

## Windows

With Git installed, run in PowerShell:

```powershell
$Checkout = Join-Path $env:LOCALAPPDATA 'GarminConnectMCP-source'
git clone https://github.com/myke239/garmin-connect-mcp.git $Checkout
& (Join-Path $Checkout 'scripts\install.ps1') -Desktop
$Garmin = Join-Path $env:LOCALAPPDATA 'Programs\GarminConnectMCP\bin\garmin-connect.ps1'
& $Garmin doctor
& $Garmin login
& $Garmin verify
& $Garmin install-plugin
```

If you already have a trusted checkout, run its `scripts\install.ps1` by absolute path instead of cloning again. The source checkout location is your choice. The installer uses an existing `uv` on
PATH or downloads Astral's official HTTPS installer into the application
directory, then obtains Python 3.13 and pinned runtime dependencies.
No credentials are requested during installation; login requires your terminal.
If local PowerShell policy blocks an unsigned script, invoke it using
`powershell -NoProfile -ExecutionPolicy Bypass -File '<absolute script path>'`
for that process only, where your organization permits it.

Use `-InstallDir 'D:\apps\GarminConnectMCP'` to override the application location.
Add `-Remote` for phone access, `-Desktop` for the setup/tray app and application
menu shortcut, or `-Secure` for optional protected Linux storage dependencies.

## Linux and WSL

Requires `sh`, `curl`, CA certificates and outbound HTTPS to Astral, GitHub and
the Python package index. A preinstalled Python is unnecessary.

```sh
checkout="${XDG_DATA_HOME:-$HOME/.local/share}/garmin-connect-mcp/source"
git clone https://github.com/myke239/garmin-connect-mcp.git "$checkout"
sh "$checkout/scripts/install.sh"
garmin="${XDG_DATA_HOME:-$HOME/.local/share}/garmin-connect-mcp/application/bin/garmin-connect"
"$garmin" doctor
"$garmin" login
"$garmin" verify
"$garmin" install-plugin
```

Use an existing trusted checkout's absolute script path if you already cloned it. Desktop support is optional (`--desktop`); headless users should omit it.
Install Codex CLI **inside Linux** before Linux plugin registration.
WSL and Windows Codex installations are separate; Windows Codex should use the
Windows launcher, not a WSL registration.

Set `GARMIN_INSTALL_DIR=/absolute/custom/path` for an alternate application
directory. Use `--remote` for tunnel dependencies, `--desktop` for setup/tray and an app-menu
shortcut, and `--secure` for optional Linux encryption dependencies. Linux downloads
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
`-m garmin_connect_mcp.manage serve`. Plugin registration uses that same interpreter
and copies manifests/skills into the installed release; it does not rewrite the
source checkout's `.mcp.json`.

For phone access, run the installer with remote extras, then `tunnel-setup` and
`tunnel`. Follow [personal HTTPS setup](chatgpt.md) for ChatGPT connection and consent.
Keep the PC awake and service running. Writes are enabled by default when no local policy exists; installation preserves explicit disable/allowlist settings and never approves OAuth or upgrades remote grants. Use writes-disable or an operation allowlist to restrict local access.

## Update, remove and troubleshooting

Re-run the installer from the desired reviewed release, then `install-plugin`
to refresh local tools/skills. Registration replaces only the known one-plugin
`myke-garmin` marketplace and restores its previous source if the switch fails.
Unexpected additional plugins stop migration before removal. Restart your tunnel deliberately after checking
which runtime owns it. Open a fresh Codex chat. Preserve credentials and journals.
There is no automatic update or cleanup. Background startup is a separate opt-in command.

Remove Codex registration with
`codex plugin remove garmin-connect@myke-garmin`. After stopping services, application
files can be removed separately; keep the data directory unless intentionally
revoking/removing local sessions. Failed installation release directories are
retained for diagnosis and can be removed once verified unused.

If `doctor` reports no session, login in the environment you intend to run.
If plugin registration reports missing Codex, put the Codex CLI on that platform's
PATH. TLS failures must be resolved with trusted CA configuration or narrowly
scoped antivirus exceptions; TLS verification is never disabled.

## Verified installation coverage

Version 0.12.0 was installed on Windows and Ubuntu 22.04 under WSL2 with managed Python 3.13.16. Both installed runtimes passed MCP handshakes, discovery of 44 default tools, schema lookup and unauthenticated HTTP rejection. Windows retained and verified its Garmin session; Linux installation tests used no account credentials. The final WSL offline suite passed 419 tests. Windows/Linux executable and Docker protocol checks passed in CI.

Run the installed Python from `installation.json` against `scripts/verify_install.py`, passing the receipt path, to repeat the isolated offline checks. Historical results are retained in [verification history](../development/verification-history.md).

## Executables and desktop setup

Download a platform build from [GitHub releases](https://github.com/myke239/garmin-connect-mcp/releases).
Extract the entire bundle, including _internal. Windows users open
`garmin-connect-desktop.exe`, then choose **Install this app locally**. Linux users
run the extracted `garmin-connect install-local`, then open Garmin Connect MCP from
the application menu or use the absolute executable printed by installation.
The console executable accepts doctor/login/verify/install-plugin/serve and all
other launcher commands. A managed-Python installation opens the same setup
window using its launcher `desktop --tray`. Installation preserves old releases
and existing credentials, grants and journals.

The public frozen build excludes Garmin's separately licensed official FIT SDK.
Download links and checksums are on the release page. Use `doctor` to confirm the extracted version before installing.

Choose **Install FIT support** in the setup app or run the executable `fit-setup`.
That obtains managed Python and the SDK directly from PyPI into the application's
fit-support directory. No activation or checkout is needed. Normal source/managed
installations already obtain that dependency directly. Review Garmin's FIT
Protocol License Agreement; this project's MIT license does not replace it.

Frozen builds are unsigned and target Windows x64 and Linux x86-64 with glibc
2.35 or newer. macOS/ARM frozen builds have not been tested. Linux graphical mode
needs a display, X11/Tk libraries and a supported tray host; CLI operation remains
available on headless systems. Keep all bundle files together.

## Optional background operation

`background-start` starts only the managed tunnel; `background-stop` sends its
own instance a stop request and never kills an unrelated PID. An occupied port
prevents starting another service. `background-status` and `diagnostics` report
process state and whether localhost MCP rejects unauthenticated calls with 401.
After a 30-second grace period, three failed checks 10 seconds apart restart the
owned child. The watchdog attempts at most four launches with backoff.

`background-install` enables startup on user sign-in without starting now.
Windows uses a per-user Startup entry; Linux uses a systemd user unit with restart
limits. `background-uninstall` removes only the project's owned entry. Re-register
startup after upgrading so it points to the new release. A Secret Service keyring
must already be unlocked in the service's D-Bus session. Installation never
silently enables startup or overwrites an existing write policy. New installations allow writes by default. PCs must remain awake for phone
access; close the setup window to the tray or exit without stopping the service.

## Build executables and use Docker

Build your own executables from a reviewed source checkout with `pip install -e '.[dev,desktop,package,remote,secure]'`
and `python -m PyInstaller scripts/garmin-connect.spec`. The spec excludes the FIT
SDK and retains dependency source/license metadata. Run scripts/verify_frozen.py
against the console executable. CI independently builds Windows and Linux and
constructs the desktop UI.

For Docker, build `docker build -t garmin-connect-mcp .`, then use
`docker run --rm -i garmin-connect-mcp serve` for stdio. The image runs as UID 10001.
Use a private volume at /home/garmin/.local/share/garmin-connect-mcp and log in
interactively with `docker run --rm -it -v garmin-data:/home/garmin/.local/share/garmin-connect-mcp garmin-connect-mcp login`.
Windows DPAPI credentials cannot be reused in Linux containers. The image is built
locally; no prebuilt image embedding Garmin's FIT SDK is published. Container
phone access uses the normal OAuth/ngrok flow and private tunnel token. The CLI
and Docker docs do not grant Garmin write scope automatically.

## Publisher identity and Windows installer

Current 0.13.0 release executables are unsigned. The new Das Kreb installer/signing work is described in [trusted distribution](../development/distribution.md); signed publisher status requires completed identity validation and a verified signed release. Do not treat the vendor name/icon as a signature.
