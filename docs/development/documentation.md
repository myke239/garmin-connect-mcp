# Documentation maintenance

[Documentation home](../README.md)

## Structure

Keep the root README focused on purpose, concrete use cases, benefits, a short starting path and honest limits. Keep core project files (LICENSE, NOTICE, VERSION, CHANGELOG, CONTRIBUTING and AGENTS.md) at the root. Runtime/build configuration is also naturally at the root; task-specific documentation belongs under `docs/`.

| Directory | Purpose |
| --- | --- |
| `docs/getting-started/` | Installation and client connection journeys |
| `docs/guides/` | Tasks and troubleshooting |
| `docs/reference/` | Tools, schemas, units, limits and catalog assets |
| `docs/development/` | Contributor guidance, dated evidence and roadmap |

Every guide links back to `docs/README.md`. Link to the canonical explanation rather than appending the same release notes to multiple guides. Preserve historical evidence with its tested version/date, and put current status above it. Avoid personal machine paths, except explicitly marked legacy-data compatibility notes. Skills stay next to the plugin; they are operational agent instructions, not duplicated user manuals.

Describe this project through concrete capabilities, workflows and verified limits. Do not include direct comparisons with other projects or an alternatives/tradeoffs page.

## Checks before merging

```text
python scripts/check_docs.py
python scripts/check_secrets.py
```

The documentation checker verifies local Markdown targets and heading fragments, code-fence balance, core-root layout and the live offline default tool inventory and parameter names against the reference. It performs no network or account calls. Remote URLs require a separate manual source review; this check does not prove an external page is available.

For a changed install command or schema example, verify against the launcher/parser or offline MCP contract. Runtime changes still need appropriate tests. Documentation-only changes retain VERSION; update CHANGELOG under Unreleased. Preserve encrypted journals, private audits and active installed runtimes.

The tool reference is based on offline `create_server(tool_profile="all").list_tools()` for 0.13.0. Refresh names/parameters when tools change. Never equate Garmin readback or queueing with physical watch execution.
