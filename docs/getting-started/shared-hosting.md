# Several MCP servers, one HTTPS hostname

[Documentation home](../README.md) · [ChatGPT setup](chatgpt.md)

Use one ngrok tunnel to one loopback gateway. The gateway forwards requests by
path to separate servers. Each service owns its OAuth issuer, token audience,
consent flow and protected-resource metadata. A common hostname does not make
tokens interchangeable.

| Service | Example connection URL | Backend |
| --- | --- | --- |
| Garmin 0.19+ | `https://YOUR-HOST/mcp/garmin-connect/` | `127.0.0.1:8787` |
| Existing MyFitnessPal gateway | `https://YOUR-HOST/myfitnesspal/mcp` | gateway on `127.0.0.1:8788` |

MyFitnessPal's existing path stays unchanged. Enter each complete URL as a
separate ChatGPT plugin. Keep the trailing slash on the Garmin URL.

## Using the MyFitnessPal companion gateway

Use the updated gateway from the
[MyFitnessPal connector](https://github.com/myke239/myfitnesspal-mcp), which starts
the Garmin backend and forwards its routes. Its Garmin readiness check requires
0.19.0 or later. The gateway accepts Garmin's bounded 3 MiB MCP requests and
retains the existing MyFitnessPal namespace and OAuth state.

```powershell
# Use the installed Python paths from your own installation receipts.
& '<MyFitnessPal Python>' -m myfitnesspal_mcp.gateway `
  --garmin-python '<Garmin Python>' `
  --garmin-data '<Garmin private data directory>'
```

The current companion gateway reads the previously configured public origin
from Garmin's legacy OAuth state and the saved ngrok token. It is an existing-
installation integration, not a general first-install wizard. It does not
silently move OAuth grants. For a new shared installation use the explicit
reverse-proxy setup below. Never paste token files into chat.

## Using another gateway or reverse proxy

Start Garmin as a backend only. `remote-serve` opens no ngrok tunnel:

```powershell
& $Garmin remote-serve --public-url https://YOUR-HOST --port 8787
& $Garmin connection-info --public-url https://YOUR-HOST
```

Configure your gateway to preserve these paths exactly:

| Forward to Garmin | Purpose |
| --- | --- |
| `/mcp/garmin-connect` and `/mcp/garmin-connect/*` | MCP, consent, authorization, token, registration, revocation and health |
| `/.well-known/oauth-authorization-server/mcp/garmin-connect` | OAuth issuer discovery |
| `/.well-known/oauth-protected-resource/mcp/garmin-connect/` | MCP protected-resource discovery |

Preserve the public **Host** header. Do not strip the Garmin prefix, rewrite the
trailing slash, cache responses, or supply an internal hostname. Forward query
strings and streaming responses; allow bounded 3 MiB MCP bodies. The backend
rejects other Host/Origin values and binds only to loopback.

For example, a Caddy gateway listening locally on 8788 can use:

```caddyfile
http://127.0.0.1:8788 {
    @garmin path /mcp/garmin-connect /mcp/garmin-connect/* /.well-known/oauth-authorization-server/mcp/garmin-connect /.well-known/oauth-protected-resource/mcp/garmin-connect/
    reverse_proxy @garmin 127.0.0.1:8787
    # Add the other connector's complete routes and metadata here.
}
```

Point your one ngrok HTTPS endpoint at port 8788. Match your reserved hostname
to `--public-url`. This is an illustrative proxy configuration; Caddy is not
installed or managed by Garmin. Each other connector still needs its own auth.

## Upgrade and diagnose

Stop/restart only the service tree you own after updating its installed runtime.
Do not run `tunnel` or `background-start` alongside an already running shared
gateway. Windows error 10048 means the socket is occupied; it is not a Garmin
login error. Keep an active gateway running while investigating ownership.

A healthy unauthenticated POST to the Garmin MCP URL returns **401**, with
`WWW-Authenticate` pointing to the namespaced metadata. That metadata must name
`https://YOUR-HOST/mcp/garmin-connect/` as resource and
`https://YOUR-HOST/mcp/garmin-connect` as authorization server. MyFitnessPal must
advertise its own resource/issuer. A 404 suggests path routing; a 502/503 suggests
an unavailable backend; invalid-target suggests a URL/token audience mismatch.

Old Garmin `/mcp`, root OAuth routes and root metadata are migration aliases only
when old saved OAuth state exists. A generic proxy must explicitly forward those
old routes if existing connections still depend on them. Fresh installations do
not claim them. Never reset OAuth state just to change the path.
