# Roadmap and current status

[Documentation home](../README.md)

The four comparison-report **software phases shipped in 0.12.0** through [issue #20](https://github.com/myke239/garmin-connect-mcp/issues/20). Each used a feature branch, offline checks, bounded opt-in live tests where meaningful, and a reviewed PR/merge.

| Phase | Delivered | Contribution |
| --- | --- | --- |
| 1 | Recovery/context and running, strength/timed and swimming builders | [PR #21](https://github.com/myke239/garmin-connect-mcp/pull/21) |
| 2 | Local FIT archive, richer samples, interval/power/drift analysis and clone/rename/delete/calendar batches | [PR #22](https://github.com/myke239/garmin-connect-mcp/pull/22) |
| 3 | Operation allowlists, tool profiles, optional Linux Secret Service storage and catalog drift checks | [PR #23](https://github.com/myke239/garmin-connect-mcp/pull/23) |
| 4 | Desktop setup, optional background/startup controls, Docker/executables, diagnostics and quality CI | [PR #24](https://github.com/myke239/garmin-connect-mcp/pull/24) |

Windows and WSL 0.12.0 installations passed installed MCP/HTTP guard checks. The final WSL suite passed 419 tests; all Windows/Linux Python, installer, executable, container and quality CI jobs passed. The Windows Garmin session and public OAuth read/write metadata were preserved. Live recovery, builder, catalog and lifecycle acceptance/cleanup are described in [verification history](verification-history.md) and [write audit](write-audit.md).

## Remaining verification and scope

Physical watch execution requires owner evidence after sync; server readback cannot prove animation or device execution. macOS/ARM frozen distributions have not been tested. A headless Linux protected store requires an available unlocked Secret Service session.

Official Garmin developer OAuth and a hosted multi-user service remain outside this personal connector. They require developer access and a separately reviewed tenant architecture. The [partner API experiment](../../gpt-actions/README.md) is deferred, not an installation option.

Further changes should begin with an issue describing the concrete workflow and evidence required. Keep credentials, journals and private audit output out of public contributions.
