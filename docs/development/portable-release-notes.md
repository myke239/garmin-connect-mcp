# Garmin Connect MCP 0.19.0

New connections use **`/mcp/garmin-connect/`**. One HTTPS hostname can serve Garmin
and MyFitnessPal through a path-routing gateway, with separate OAuth issuers and
token audiences. Existing `/mcp` grants continue through compatibility routes;
create a new connection to migrate, without resetting saved credentials.

- Illustrated installation and ChatGPT guides, with actual Windows setup images.
- Clear Codex versus ChatGPT setup and shared-hosting instructions.
- Desktop URL helper and backend-only `remote-serve` / `connection-info` commands.
- Actionable occupied-port and missing-Codex errors.
- Includes the training/recovery, Lifestyle write and sleep/correction tools
  developed since the previous downloadable release. See CHANGELOG and tool reference.

Download the Windows x64 ZIP or Linux x86-64 TAR.GZ, verify SHA256SUMS, and extract
the entire archive. The binaries are **unsigned**; no verified publisher or signed
Windows installer is claimed. Integrity JSON records include source commit,
bundle hashes and a clearly scoped build-environment inventory. The public
executables exclude Garmin's separately licensed FIT SDK; use `fit-setup` locally.

Install: https://github.com/myke239/garmin-connect-mcp/blob/main/docs/getting-started/installation.md

Shared host: https://github.com/myke239/garmin-connect-mcp/blob/main/docs/getting-started/shared-hosting.md

The portable-release workflow requires successful CI on the exact main commit,
then builds and verifies both platforms before publishing. Account writes are
not exercised by CI. Existing local policies and OAuth scopes remain effective.
