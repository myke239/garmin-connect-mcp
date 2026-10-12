# Local plugin design and verification

The compatibility package lives at `plugins/garmin-connect`: manifest, local
stdio MCP configuration, a training-analysis skill, and a workout creation and
scheduling skill, plus account management for activities, measurements, imports
and device delivery. The workout skill includes a validated running JSON example,
SDK field conventions, preview/commit consent, and ambiguous-outcome handling.
`.agents/plugins/marketplace.json` exposes it through the local `myke-garmin`
catalog. There are no lifecycle hooks, new listening ports, or automated uploads.

The new [per-user installer](INSTALL.md) installs an isolated runtime and copies
the plugin marketplace without changing source manifests. Its launcher provides
`install-plugin` on Windows/Linux. The legacy development installer below
remains supported.

Development installation deliberately reuses the tested project environment instead of
copying dependencies into the plugin cache. `scripts/install_plugin.ps1` resolves
the interpreter for each checkout and writes its absolute path into `.mcp.json`.
This makes the package independent of the chat's working directory. The Windows
launcher configuration is machine-specific and is regenerated when installed on
another machine. Source stays in your checkout; Codex controls its normal cache.

Authentication remains in the MCP server's encrypted session store. The package
contains no tokens or account statistics. A new computer needs its own login.

Local skills load in Codex. A ChatGPT HTTPS MCP connection does not receive
these local files. For a ChatGPT conversation, supply the workout skill body
and its schema reference as instructions/context when needed; server validation
and MCP tool descriptions apply to every client regardless of skill loading.
Version 0.3 also exposes operation contracts and verification through MCP tools,
so ChatGPT agents can obtain exact field/SDK guidance without local skill files.

## Current verification (0.8.0)

- The marketplace installs `garmin-connect@myke-garmin`; the installed skills
  were compared with the merged source.
- MCP discovery exposes 30 tools, including four operation-specific workout
  commits, yoga pose discovery and timed pose construction.
- 357 offline tests passed locally and CI passed on Windows/Linux.
- Live stdio reads/cache and authenticated HTTPS discovery passed. Read-only
  grants reject all commit tools. Live synthetic creation, replacement,
  scheduling and calendar-batch commits passed; fixtures were removed.
- The owner reported that 0.8.0 resolved the previously blocked ChatGPT workflow
  in their case. This does not establish a universal safety-classifier fix.

See [PHASES.md](PHASES.md) for historical gates and [WRITE_AUDIT.md](WRITE_AUDIT.md),
[SPORTS.md](SPORTS.md) and [YOGA_POSES.md](YOGA_POSES.md) for coverage and limits.
A fresh Codex chat loads updated tools/skills. ChatGPT may require reviewing and
refreshing its saved tool definitions; local skill files are not transferred.

To repeat the installed-package live check (explicit, account-reading operation):

```powershell
.\.venv313\Scripts\python.exe scripts/verify_live.py --plugin-root '<installedPath from codex plugin add --json>'
```

The `browse-garmin-exercises` skill handles standalone catalog browsing, exact
movement lookup and pagination. ChatGPT remote connections receive equivalent
quick-start instructions in the MCP tool description; local skill files are
loaded by Codex. Refresh the client tool list after a server update.

Workout and account-management skills use complete per-sport/per-activity schemas
and readonly builders. The same workflow guidance is exposed through remote MCP
tool descriptions and queryable contracts. See [SPORTS.md](SPORTS.md).

## Update and remove

Update the checkout through a reviewed PR, install the updated package into the
same interpreter (`python -m pip install -e '.[dev,remote]'` using that interpreter),
and run `scripts/install_plugin.ps1` again. A running HTTPS process must be
restarted to load changed server code; preserve its encrypted OAuth state.
Open a fresh Codex chat and refresh ChatGPT's plugin definitions when tools change.

Remove the local plugin with `codex plugin remove garmin-connect@myke-garmin`.
This removes the Codex plugin registration, not the encrypted Garmin session,
OAuth grants or an independently running HTTPS tunnel. For remote revocation,
see [REMOTE.md](REMOTE.md).
