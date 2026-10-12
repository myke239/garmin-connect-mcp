# Troubleshooting

[Documentation home](../README.md)

Start with the installed launcher's `doctor`, `verify` and, for HTTPS, `diagnostics`/`background-status`. `doctor` and diagnostics are offline/state checks; only `verify` contacts Garmin to verify the saved session. Do not publish session files, tokens or private journal payloads.

| Symptom | Check and next step |
| --- | --- |
| `ModuleNotFoundError: garmin_connect_mcp` | You may be invoking a different Python environment. Use the installed absolute launcher from the installation guide; no activation or `cd` is needed. |
| `AUTH_REQUIRED` | Run `login` and `verify` in the same OS/runtime and private data directory used by the client. Never put Garmin credentials in chat. |
| New tools or skills are missing | Reinstall the reviewed version, run `install-plugin`, restart an old HTTPS process deliberately, then open a fresh Codex chat. Smaller tool profiles intentionally omit tools. |
| `WRITES_DISABLED` / `WRITE_OPERATION_DENIED` | Review local write settings with `writes-status`; enable only desired operations. An MCP request cannot change this owner policy. |
| `WRITE_SCOPE_REQUIRED` / OAuth `invalid_scope` | Local policy and remote scope are separate; default-enabled local writes do not upgrade a read-only grant. Select both `garmin:read` and `garmin:write`; an old read-only client registration may need a fresh connection. See personal HTTPS setup. |
| Scheduling rejects arguments | Query the current write schema. Use `workout_id` and `date_str`, not `workoutId` or `date`; inspect the calendar before preparing duplicates. |
| `WORKOUT_TARGET_CHANGED` | Read a fresh mutation target and review a new intent. The reviewed name/hash no longer matches Garmin. |
| `DRAFT_EXPIRED` | If no mutation was sent, review a newly prepared intent. Drafts expire after 30 minutes. |
| `unknown` / `in_progress` / partial batch | Inspect `get_garmin_write_status` and Garmin readback. Preserve the journal; do not use a new key or delete state to force a retry. |
| OpenAI safety checks block a call | Preserve the exact tool error, timestamp and conversation/request ID. A block without a server response is not proof of bad Garmin scopes. Do not switch paths to bypass it. |
| `FIT_SUPPORT_REQUIRED` in an executable build | Run the installed executable `fit-setup` or choose Install FIT support in the desktop app. Source installations already obtain the SDK directly. |
| `ARCHIVE_DISABLED` / `ARCHIVE_NOT_FOUND` | Opt in locally with `archive-enable`, then archive the selected activity. Disabling access preserves records. |
| Missing wellness values or unavailable analytics | Check device availability, original timestamps and recording continuity. Missing values are not zero; sparse recordings cannot support every analysis. |
| TLS/certificate errors | Use trusted system CA configuration and narrowly scoped antivirus exceptions where appropriate. Keep TLS verification and protection enabled. |
| Background service cannot start | Check the saved tunnel token, remote dependencies and port ownership. The service refuses an occupied port and will not kill another process. |
| Linux protected storage is unavailable | Verify the same D-Bus session has an unlocked supported Secret Service keyring. Do not copy Windows DPAPI credentials into Linux. |

## Report an actionable issue

Include the version, OS, installation type, client, selected tool profile, exact tool name and argument *shape*, safe error code, and whether a mutation reached Garmin. Use synthetic examples; omit real identifiers if unnecessary. State whether the failure occurred during preparation, commit or readback. Historical verification is in [the write audit](../development/write-audit.md).

For a private security concern, follow [CONTRIBUTING](../../CONTRIBUTING) rather than posting credentials or exploit details publicly.
