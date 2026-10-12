# Personal HTTPS access

The optional remote service exposes the read tools and opt-in previewed writes through
Streamable HTTP at `/mcp`. It requires OAuth with PKCE and explicit approval in
the owner's local terminal. Garmin credentials never go to ChatGPT or ngrok.
Ngrok carries the HTTPS traffic, including tool responses, so it is a trusted
transport provider. Your PC and the tunnel process must remain running.

## Install and start (Windows)

```powershell
cd garmin-connect-mcp
.\.venv\Scripts\python.exe -m pip install -e '.[remote]'
.\.venv\Scripts\python.exe -m garmin_connect_mcp.tunnel setup
.\.venv\Scripts\python.exe -m garmin_connect_mcp.tunnel run
```

Setup prompts for the ngrok authtoken without echoing it. Tokens and remote
OAuth state use Windows account encryption in the existing private data
directory. The launcher reserves a loopback socket before opening the tunnel.
It prints the public MCP URL; `tunnel status` also reports the URL and process ID.
Ctrl+C closes the foreground server and tunnel. No startup task is installed.

## Connect ChatGPT

Open https://chatgpt.com/plugins on the web, select + then Add custom MCP server,
and enter the printed HTTPS URL. Select OAuth, then Dynamic Client Registration
(DCR); leave static client ID and secret blank, and keep `garmin:read` selected.
Use the name **Garmin Connect**. For opt-in writes, also select `garmin:write`.
New DCR registrations that omit scope support both scopes, but tokens receive
only the scopes approved through local consent. Explicit read-only registrations
remain read-only. If authorization reports that the client was not registered
with `garmin:write`, delete that ChatGPT connection and create a fresh one with
both scopes selected; reconnecting the old client does not change its registration.
The CIMD-unavailable notice is informational; this server supports DCR.
Create the plugin and install it. Availability
depends on your account and workspace. When the connection opens its consent
page, paste the entire approval command shown there into PowerShell on the PC
running the server. It uses that installation's absolute Python path and works
from any folder, without activating a virtual environment. Then
review the callback and type `APPROVE`. Return to the page and select Continue.
Only ChatGPT callback URLs are permitted. Connection requests expire after five
minutes; restart authorization if needed.

After installation, verify access in a new ChatGPT conversation, then check the
app on your phone. Phone availability must be checked with your account; a
successful local test does not establish mobile support.

## Revoke and troubleshoot

```powershell
.\.venv\Scripts\python.exe -m garmin_connect_mcp.remote reset
```

Type `RESET` to revoke all remote tokens and registrations. This preserves the
local Garmin login. Stop the tunnel process to disable public access entirely.
If ngrok assigns a different origin, reset remote state and reconnect ChatGPT.
The server rejects origin changes instead of moving existing grants silently.

Unauthorized `/mcp` requests return 401. Public health and OAuth metadata reveal
no Garmin data. Access tokens expire after an hour; rotated refresh tokens have
a 30-day lifetime. MCP requests have a 3 MiB HTTP body limit (activity-file payloads are limited to
2 MiB decoded); OAuth requests have a 16 KiB limit. Bounded concurrency and a
shared 120-per-minute limit apply. Access logging is disabled. This is a single-owner
service, not a multi-user public Garmin integration.

Offline tests cover discovery, local consent, PKCE, code replay, resource binding,
refresh rotation, revocation, expiry and HTTP boundary checks. Public tunnel and
ChatGPT connection checks require the owner's ngrok token and account.

## Troubleshooting HTTPS inspection

If antivirus HTTPS inspection replaces ngrok certificates or damages HTTP
response framing, use narrowly scoped Web Shield exceptions for the ngrok
agent hostname, your assigned public hostname and your loopback port.
Keep antivirus protection and TLS certificate validation enabled.


## Account writes

See [WRITES.md](WRITES.md). Enable writes locally, refresh the ChatGPT tool list,
and reconnect with both garmin:read and garmin:write. Existing read-only tokens
are not upgraded. Review every draft before commit.

## Server updates and safety-block diagnosis

Restart the HTTPS service after server-code updates and verify the printed origin
matches the registered ChatGPT URL. Keep existing encrypted sessions/grants; an
ordinary update does not require resetting OAuth. Refresh/review the plugin's
saved tool definitions when they change. Existing read-only clients still need
explicit write authorization; refreshing tools alone does not expand scopes.

Version 0.8.0 returns copy-ready operation-specific commit arguments from workout
preparation. Approve the full preview and pass those arguments unchanged. If
ChatGPT says a call was blocked by OpenAI safety checks without a server response,
preserve the exact message and inspect durable draft status. A working direct
MCP diagnostic does not establish that ChatGPT's classifier will permit a call.
Do not switch execution paths to evade a platform block. The owner reported
success after the 0.8.0 update; this is one case, not a guaranteed remedy.

## Installed launchers (0.8.1)

[INSTALL.md](INSTALL.md) provides Windows/Linux per-user setup. Include remote
extras, then use the full launcher path with `tunnel-setup`, `tunnel` and
`approve <ticket>` instead of activating Python or changing directories.
The current HTTPS process and credentials are not moved by installation.
Linux session files use owner-only permissions rather than DPAPI encryption.
