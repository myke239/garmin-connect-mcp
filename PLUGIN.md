# Local plugin design and verification

The compatibility package lives at `plugins/garmin-connect`: manifest, local
stdio MCP configuration, and one narrowly scoped training-analysis skill.
`.agents/plugins/marketplace.json` exposes it through the private `myke-garmin`
catalog. There are no lifecycle hooks, new listening ports, or automated uploads.

Installation deliberately reuses the tested project environment instead of
copying dependencies into the plugin cache. `scripts/install_plugin.ps1` resolves
the interpreter for each checkout and writes its absolute path into `.mcp.json`.
This makes the package independent of the chat's working directory. The Windows
launcher configuration is machine-specific and is regenerated when installed on
another machine. All project work stays on D:; Codex controls its normal cache.

Authentication remains in the MCP server's encrypted session store. The package
contains no tokens or account statistics. A new computer needs its own login.

Verification gates performed on this machine:

1. Codex accepted the marketplace and installed/enabled `garmin-connect@myke-garmin`.
2. After removing the old standalone registration, `codex mcp list --json`
   resolved the plugin's server with its 30-second startup and 240-second tool timeout.
3. An MCP client launched the configuration from the installed plugin copy and
   passed discovery of seven read-only tools, live run/detail/splits/heart-rate
   samples/training summary reads, and cache verification. No private data was printed.
4. All 35 offline server tests passed. The training skill was separately validated.

The current conversation may retain the previous tool instance. A fresh chat or
application restart loads the installed plugin's tools and skill; that desktop
reload still needs to happen. It is separate from the verified installed package
and live protocol checks.

To repeat the installed-package live check (explicit, account-reading operation):

```powershell
.\.venv313\Scripts\python.exe scripts/verify_live.py --plugin-root '<installedPath from codex plugin add --json>'
```
