# Fit, tradeoffs and alternatives

[Documentation home](README.md)

Garmin Connect contains useful data and a workout library, but an assistant needs more than a broad SDK wrapper to use them accurately. This connector combines bounded training reads, maintained workout builders, catalog discovery and an accountable write workflow. You can move from “what happened?” to “prepare this session for next week” without exporting data by hand or inventing exercise identifiers.

## Where it adds value

**For runners and swimmers:** relate sessions to sleep/HRV and recovery, compare equivalent laps, and draft interval or pool sessions with explicit units. Recorded FIT analysis is opt-in and reports unavailable results when samples cannot support an estimate.

**For strength and yoga planning:** discover exact catalog pairs, build rep-based or custom timed steps, and keep the requested exercise selection. The yoga list records live acceptance of all 85 pose identifiers, with clear limits around animation and watch execution.

**For agents and maintainers:** query contracts before writing, verify saved templates before scheduling, and inspect durable status after a timeout. Schema validation, bounded payloads, target checks and a journal support the assistant's review workflow across clients. These controls reduce mistakes; they cannot guarantee an external service or model never fails.

**For a personal self-hosted setup:** run stdio locally, narrow the exposed profile, and optionally add OAuth-protected HTTPS for a supported ChatGPT account. The desktop app and absolute launchers reduce repeated environment setup. Garmin passwords are entered locally, not supplied to the model.

## Compared with other open-source approaches

This is a comparison of project emphasis, not a claim of exclusivity or a ranking. Repository documentation was reviewed on **2026-10-12**; projects can change.

| Project | Publicly described focus | What to weigh against this connector |
| --- | --- | --- |
| [goosegit97/garmin-mcp](https://github.com/goosegit97/garmin-mcp) | Local stdio in a single Go binary, native strength/pool-swim workouts and wellness reads. | A smaller native binary may be attractive. This project offers a Python SDK stack with reviewed lifecycle writes, catalog evidence, optional personal HTTPS and desktop setup. |
| [NoaMatout/garmin-mcp](https://github.com/NoaMatout/garmin-mcp) | Local FIT ingestion, DuckDB, typed analysis tools and structured workout export. | A local analytical database may suit deeper exploration. This project's bounded archive is not a DuckDB query engine; it connects directly to Garmin Connect and manages saved templates/calendars. |
| [Taxuspt/garmin_mcp](https://github.com/Taxuspt/garmin_mcp) | Direct Garmin health/activity tools and workout upload/scheduling through MCP. | Broad API access and straightforward authentication may fit a simpler workflow. Here the focus includes prepared intents, explicit target hashes and journaled partial outcomes. |

Workout creation, wellness access, FIT analysis and local operation exist elsewhere too. The reason to choose this project is the combination of those capabilities with agent guidance, verified catalogs and reviewable account management—not the tool count alone.

## Costs and limitations

- You run and maintain it. Personal phone access needs a running PC, ngrok and a compatible ChatGPT account; there is no hosted service or public marketplace approval.
- It uses an unofficial SDK rather than Garmin partner OAuth. Garmin changes can break compatibility and require updates.
- It is a Python application with optional dependencies. Public executables simplify core setup, but FIT support requires a separately obtained local SDK due to Garmin's license.
- Archives provide specific bounded analyses, not a general SQL database or independently calculated training-load model. Missing data is not filled in.
- Readback verifies Garmin storage, not watch animation or physical execution. macOS/ARM executable builds are unverified.
- Codex loads local skills; a ChatGPT MCP connection receives server descriptions/contracts, not the skill files themselves.

See [installation](getting-started/installation.md), [data and limits](reference/data-and-limits.md) and [verification history](development/verification-history.md) for the evidence behind these choices.
