# Garmin Connect MCP 0.20.1

Fixes the blank Server URL field in setup. The visible URL now remains available
and matches the value copied to the clipboard.

**Windows: download GarminConnectSetup.exe, open it, and select Begin Install.**
The app guides Garmin sign-in, verification codes, ChatGPT/Codex connection and
the final connection check. No terminal, Python or Git is required.

- One setup task per page, with Next/Save/Approve actions and inline errors.
- Reuse an existing shared HTTPS address at `/mcp/garmin-connect/`.
- Approve the exact browser connection code locally, with access details shown.
- Automatically obtain and checksum-verify the official Codex helper when needed.
- A short illustrated guide; Linux/macOS scripts and advanced instructions remain
  separate.
- Executable checksums alongside archive checksums and integrity records.

[Installation guide](https://github.com/myke239/garmin-connect-mcp/blob/main/docs/getting-started/installation.md)

Downloads are **unsigned**; a verified publisher is not claimed. The Windows
installer and Linux/Windows portable builds pass isolated installation or MCP
checks before publication. Default tests and CI do not use Garmin account data.
Existing write policies and remote OAuth scope requirements remain effective.

The public executable excludes Garmin's separately licensed FIT SDK. Optional
FIT support remains available through the advanced `fit-setup` command.
