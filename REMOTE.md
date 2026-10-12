# Personal HTTPS access

The optional remote service exposes the same seven read-only tools through
Streamable HTTP at `/mcp`. It requires OAuth with PKCE and explicit approval in
the owner's local terminal. Garmin credentials never go to ChatGPT or ngrok.
Ngrok carries the HTTPS traffic, including tool responses, so it is a trusted
transport provider. Your PC and the tunnel process must remain running.

## Install and start (Windows)

```powershell
cd D:\developer\garmin-connect-mcp
.\.venv313\Scripts\python.exe -m pip install -e '.[remote]'
.\.venv313\Scripts\python.exe -m garmin_connect_mcp.tunnel setup
.\.venv313\Scripts\python.exe -m garmin_connect_mcp.tunnel run
```

Setup prompts for the ngrok authtoken without echoing it. Tokens and remote
OAuth state use Windows account encryption in the existing private data
directory. The launcher reserves a loopback socket before opening the tunnel.
It prints the public MCP URL; `tunnel status` also reports the URL and process ID.
Ctrl+C closes the foreground server and tunnel. No startup task is installed.

## Connect ChatGPT

In ChatGPT's web settings, enable developer mode if available and add a custom
MCP app using the printed HTTPS URL and OAuth authentication. Availability
depends on your account and workspace. When the connection opens its consent
page, run the exact approval command shown there in your local PowerShell,
review the callback and type `APPROVE`. Return to the page and select Continue.
Only ChatGPT callback URLs are permitted. Connection requests expire after five
minutes; restart authorization if needed.

After installation, verify access in a new ChatGPT conversation, then check the
app on your phone. Phone availability must be checked with your account; a
successful local test does not establish mobile support.

## Revoke and troubleshoot

```powershell
.\.venv313\Scripts\python.exe -m garmin_connect_mcp.remote reset
```

Type `RESET` to revoke all remote tokens and registrations. This preserves the
local Garmin login. Stop the tunnel process to disable public access entirely.
If ngrok assigns a different origin, reset remote state and reconnect ChatGPT.
The server rejects origin changes instead of moving existing grants silently.

Unauthorized `/mcp` requests return 401. Public health and OAuth metadata reveal
no Garmin data. Access tokens expire after an hour; rotated refresh tokens have
a 30-day lifetime. Requests have a 16 KiB body limit, bounded concurrency and a
shared 120-per-minute limit. Access logging is disabled. This is a single-owner
service, not a multi-user public Garmin integration.

Offline tests cover discovery, local consent, PKCE, code replay, resource binding,
refresh rotation, revocation, expiry and HTTP boundary checks. Public tunnel and
ChatGPT connection checks require the owner's ngrok token and account.
