# Garmin Connect MCP

**Turn your Garmin history into useful training conversations—and reviewed workouts you can save to Garmin Connect.**

Bring your runs, recovery metrics, strength sessions and workout library into Codex or another MCP assistant. Ask what changed in your training, build a structured session with real Garmin exercise identifiers, then review it before saving or scheduling it. An optional personal HTTPS connection brings the same server tools to a supported ChatGPT account, including phone access where available.

[![CI](https://github.com/myke239/garmin-connect-mcp/actions/workflows/tests.yml/badge.svg)](https://github.com/myke239/garmin-connect-mcp/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

**[Download v0.13.0](https://github.com/myke239/garmin-connect-mcp/releases/tag/v0.13.0)** · **[Get started](docs/getting-started/installation.md)** · **[Documentation](docs/README.md)** · **[Changelog](CHANGELOG)**

## What you can do

| Your question or task | What the connector provides |
| --- | --- |
| “Compare the work intervals in these two runs.” | Activity details, splits and explicitly selected interval comparisons. |
| “How did my sleep and HRV look around this session?” | Recovery summaries joined to an activity, with missing values and dates disclosed. |
| “Build a strength session with these exercises and timed holds.” | Exact exercise discovery, rep/timed-step builders, planned loads and rests. |
| “Make a pool swim with drills, equipment and pace targets.” | A validated swimming draft with explicit pool lengths and Garmin step fields. |
| “Create a yoga sequence and schedule it for Tuesday.” | 85 verified pose identifiers, timed steps and a reviewable calendar workflow. |
| “Rename this workout and schedule my existing templates for the week.” | Fresh target checks, content hashes and individually journaled scheduling outcomes. |
| “Analyze my recorded power without treating missing samples as zero.” | An opt-in local FIT archive and bounded power-window/drift analysis. |

These are examples of requests, not permission to write. Account writes are **enabled by default**; you can disable them or allow only selected operations locally. Existing explicit disable settings are preserved. The assistant first prepares a validated draft; you review its complete preview before an approved commit.

## Why choose this connector?

The focus is the complete path from understanding a session to preparing and managing the next one:

- **Workouts with verified identities.** Search 1,527 strength identifiers and 85 yoga poses; use maintained sport schemas and higher-level running, strength and swim builders instead of guessing Garmin JSON.
- **Writes you can inspect and recover.** Separate preparation and commit, operation-specific review context, target hashes for rename/delete, and durable journals help prevent accidental repetition after an uncertain result. Partial batches are reported; they are not silently retried.
- **Privacy controls at the owner’s machine.** Garmin login stays in local prompts. Windows uses DPAPI; Linux offers optional Secret Service encryption. Tool profiles and operation allowlists let you expose a smaller surface. Activity reads omit GPS; retaining an original FIT file is a separate choice.
- **A guided first use for agents.** The Codex plugin includes focused skills. Every MCP client can query exact write contracts, catalog identifiers and workout schemas from the server itself.
- **A choice of deployment.** Windows/Linux installers and executable bundles, local stdio, optional authenticated HTTPS, desktop setup, and a locally built Docker image share the same validated tools.

Verified catalogs, training analysis and reviewable account management work together in one connector, with explicit handling of partial or uncertain outcomes.

## Start here

1. Follow the [installation guide](docs/getting-started/installation.md). Windows x64 and Linux x86-64 executable bundles are available; managed installers can obtain Python for you.
2. Run the installed launcher's `login`, then `verify`. Enter credentials and MFA only on your machine—never in chat.
3. Run `install-plugin` for Codex, then open a new chat. Other clients can use [the stdio configuration](docs/getting-started/codex.md#other-mcp-clients).
4. Try: “Use Garmin Connect to summarize my last three runs.” Review or restrict write access using the [account-write guide](docs/guides/account-writes.md).

Launchers work from any directory without activating a virtual environment. Standard application locations are `%LOCALAPPDATA%\Programs\GarminConnectMCP` on Windows and `${XDG_DATA_HOME:-~/.local/share}/garmin-connect-mcp/application` on Linux. Credentials and journals stay in a separate private data directory.

For ChatGPT and phone use, follow [personal HTTPS setup](docs/getting-started/chatgpt.md). Your account/workspace must support custom MCP connections, and your computer must stay awake with the tunnel running. This is a self-hosted, single-owner connection; there is no approved public ChatGPT marketplace listing or hosted multi-user service.

## Documentation

- [Getting started](docs/README.md#getting-started): installation, Codex and personal ChatGPT access.
- [Task guides](docs/README.md#task-guides): creating workouts, recovery, analysis, permissions and troubleshooting.
- [Reference](docs/README.md#reference): all 44 default tools, sport coverage, poses, units and limits.
- [Development](docs/README.md#development-and-evidence): contribution workflow, verification evidence and roadmap.

## Compatibility and honest limits

Version **0.13.0** uses Python **3.12+** and pinned [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) **0.3.17**. It is an independent, unofficial project; Garmin service changes can affect it.

Windows/Linux CI covers Python 3.12/3.13, installed runtimes, executable bundles, containers and quality checks. The 0.12.0 Ubuntu 22.04 WSL suite passed **419 tests**; the default-write change adds explicit policy/revocation regression coverage. Live synthetic workout acceptance, readback and cleanup are recorded separately in [verification history](docs/development/verification-history.md).

Garmin acceptance and queued device delivery do **not** prove execution or animation on your watch. Physical watch execution and macOS/ARM executable builds remain unverified. Public executables exclude Garmin's separately licensed FIT SDK; [local FIT setup](docs/getting-started/installation.md#executables-and-desktop-setup) obtains it directly when needed. Sparse recordings and unsupported sport fields are reported rather than invented.

## Contribute and get help

[Open an issue](https://github.com/myke239/garmin-connect-mcp/issues) with reproduction steps and redacted output. Read [troubleshooting](docs/guides/troubleshooting.md) first. Never upload tokens, session files, private workout exports or location data.

Contributions follow [issue → branch → PR → checks → merge](CONTRIBUTING). This project's code is [MIT licensed](LICENSE); dependencies have their own terms, listed in [NOTICE](NOTICE).
