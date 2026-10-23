# Guided installation decisions

The installation guide has four steps: download, run, follow the wizard, check
success. Advanced commands live in separate references.

## Research

Reviewed on 2026-10-23:

- [Ollama](https://github.com/ollama/ollama): prominent platform downloads and
  short installation directions.
- [LocalSend](https://github.com/localsend/localsend): direct platform downloads;
  contributor build details separated from installation.
- [PowerShell](https://github.com/PowerShell/PowerShell): platform-specific entry
  points instead of a long prerequisite sequence.
- [Microsoft wizard guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/win-wizards):
  one task per page, action-specific buttons, preserved choices and automatic
  progress. This is historical Windows guidance; those interaction principles
  inform this implementation rather than its visual styling.
- [Inno Setup run actions](https://jrsoftware.org/ishelp/topic_runsection.htm):
  launch the app automatically after installation, without a redundant finish page.

## Implemented flow

Windows setup starts with **Begin Install**, installs per user, then opens the
app automatically. The app guides Garmin sign-in/MFA, client selection,
hosting, exact-request OAuth approval and verification. Each page has one primary
action. Errors stay on the relevant page. Back preserves non-secret choices.

Existing shared HTTPS hosting uses `/mcp/garmin-connect/`; it is verified without
starting a second tunnel. New hosting accepts an ngrok authtoken in a masked field.
The browser displays a short-lived connection code. The owner pastes that exact
code into the local app, reviews the actual client/callback/scopes, and approves.
The app never chooses an arbitrary pending request.

Codex setup reuses its helper or downloads the official Windows release and
verifies GitHub's SHA-256 digest before use. No terminal or PATH changes are needed.
Garmin credentials, MFA and tunnel tokens do not enter command-line arguments.

## Verification boundaries

Offline tests use synthetic credentials, OAuth clients and transport responses.
Frozen checks exercise real MCP startup and desktop construction. Installer checks
use isolated application/private directories and verify uninstall preserves data.
Actual ChatGPT account dialogs and Garmin MFA require the owner; automated checks
do not claim those external interfaces were exercised with a live account.
