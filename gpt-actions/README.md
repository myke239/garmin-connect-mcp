# Direct Garmin GPT Actions feasibility test

Status: experimental, not authenticated or installed. No hosted service or MCP
server is added by this prototype. The existing Codex integration is unaffected.
The connection-test schema passed OpenAPI 3.1 validation with
openapi-spec-validator 0.9.0. This validates its structure, not OAuth compatibility
or account access. Validation tooling is kept in ignored project work storage.

## What was established

Garmin's public OAuth document specifies authorization-code OAuth with required
S256 PKCE: a fresh code_challenge on authorization and matching code_verifier at
token exchange. It also requires a developer application's client ID and secret.
Normal Garmin Connect login and the local unofficial-library session are not
these developer credentials.

The public OpenAI GPT Actions guide documents client credentials, authorization
and token URLs, scope and callbacks. Its example does not show PKCE parameters.
This absence does not establish that PKCE is unsupported, but direct Garmin
compatibility remains unverified. MCP OAuth documentation explicitly covers PKCE;
that is a different integration and cannot establish GPT Actions support.

The public Garmin document verifies this read-only endpoint:
GET https://apis.garmin.com/wellness-api/rest/user/id
and the response shape {"userId": "..."}. That is the only action included in
connection-test.openapi.json. No undocumented activity endpoints are guessed.
Detailed activity API documentation and application creation require portal
access. The Activity API describes FIT files and push/ping integration; whether
it supports the necessary direct on-demand workout reads still needs verification.

The ChatGPT GPT editor was opened in Codex's in-app browser, but remained blank
after one reload. No GPT was created and no account connection was attempted.

## Gated test procedure

1. Confirm approved Garmin Connect Developer Program access and a registered
   application with activity access. Obtain the official specification through
   the developer portal. Keep credentials out of this repository and chat.
2. Create a private test GPT in the ChatGPT web editor. Paste instructions.md and
   import connection-test.openapi.json into Actions. This is a custom GPT, not a
   universal plugin installation or public marketplace listing.
3. In the editor's OAuth settings, enter your own developer client ID and secret.
   Authorization URL: https://connect.garmin.com/oauth2Confirm
   Token URL: https://diauth.garmin.com/di-oauth2-service/oauth/token
   Garmin specifies fixed scopes controlled by app setup and user permissions;
   do not invent a workouts:read scope. Confirm the appropriate scope field with
   the registered app's documentation. Use form-encoded token exchange as Garmin
   documents, and confirm the editor supports client_secret in the body.
4. Register the exact callback supplied by the GPT editor with Garmin. The
   documented callback pattern is https://chatgpt.com/aip/<GPT-ID>/oauth/callback
   (the chat.openai.com equivalent is also documented).
5. Verify that Actions generates a fresh S256 code_challenge and matching
   code_verifier per login, alongside state. Do not hardcode these into a URL or
   store them in the schema. If this cannot be supported by Actions, stop: direct
   OAuth is incompatible and an auth adapter or another integration is needed.
6. With the user's consent, test getConnectedGarminUserId. Only a successful
   authenticated response passes the connection gate. Check refresh and a second
   user independently before claiming reusable multi-user access.
7. After login works, inspect the approved Activity API spec for read endpoints,
   retrieval windows, response sizes, binary FIT handling and any required
   notification recipient. Add and validate workout actions only when supported.
8. Test the private GPT in the user's phone app. Authentication and activity
   retrieval must both work before claiming mobile support. Public distribution
   needs a separate privacy and publishing review.

## Sources checked

- https://developers.openai.com/api/docs/actions/authentication
- https://developerportal.garmin.com/sites/default/files/OAuth2PKCE_1.pdf
- https://developerportal.garmin.com/developer-programs/connect-developer-api
- https://developer.garmin.com/gc-developer-program/activity-api/

No credentials, account identifiers, or private activity data are packaged here.
