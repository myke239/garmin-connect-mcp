# Project rules

Follow the phase gates in docs/development/verification-history.md. Never claim a gate passed without running
its checks. Do not advance to Garmin authentication until the MCP foundation is
verified. Never request credentials in chat or add tokens to source control.
Use fixed read and write allowlists, explicit units and bounded results.
Writes are enabled by default; honor explicit local disable/operation policies and, remotely, a separate garmin:write grant.
Develop on a feature branch, submit a PR, pass checks, then merge. Never push
feature changes directly to the default branch.
Keep protocol stdout clean. Keep live-account tests out of default tests and CI.

