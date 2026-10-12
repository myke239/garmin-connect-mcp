# Data, privacy, units and limits

[Documentation home](../README.md) · [Permissions and storage](../guides/permissions-and-storage.md)

## Where data goes

Garmin credentials/MFA are entered in local terminal prompts. Passwords are not saved. Session grants, write journals and remote OAuth state stay in the private data directory. Unset `GARMINTOKENS` to avoid the SDK's plaintext-store fallback.

Windows uses user-bound DPAPI encryption and owner/SYSTEM ACLs. Linux defaults to owner-only files; installing `--secure` adds dependencies but does not migrate credentials automatically. An explicit Secret Service migration encrypts TokenStore records with a key kept in the OS keyring. Protect backups too. Do not point Windows/Linux at the same session directory.

Tool results enter your assistant conversation. Activity reads omit coordinates; file uploads and explicitly retained original FIT recordings can contain GPS. An ngrok tunnel carries remote responses, so its terms and privacy practices matter. This is a single-owner server.

Logout clears the local Garmin session; it does not remotely revoke Garmin-issued tokens. Resetting remote OAuth is separate and does not clear the Garmin login. Removing a plugin does not stop a tunnel or erase private journals.

## Units and unavailable values

Distance/speed/elevation use metres, metres/second and metres; duration uses seconds unless a named SDK input explicitly uses minutes. Heart rate is bpm and HRV is milliseconds. Builders accept explicit kg and pace units and perform the documented conversion to Garmin fields.

Chart cadence follows its source descriptor (`cadence_raw`), not an assumed rpm unit; running may use steps/minute. FIT archive cadence keeps the SDK-decoded `cadence_rpm` field. Garmin chart descriptor factors are display metadata and are not applied a second time. Raw strength weights, threshold speed and recoveryTime retain their disclosed unverified units.

Missing readings stay unavailable. Undated endpoints report latest records with original dates, not observations fabricated for a requested date. Downsampling, partial coverage and cache metadata are disclosed. Training observations are not an independently computed CTL/ATL/TSB model or a diagnosis.

## Bounded results

| Surface | Bound or behavior |
| --- | --- |
| Activity listing | 90-day inclusive local range; 1–50 rows/page |
| Training summary | At most 500 activities; coverage disclosed |
| Activity splits / strength sets | At most 500 entries |
| Chart samples | At most 1,000 points; may be downsampled |
| Workout library | At most 50 templates/page; paginate when verifying absence |
| Builders | At most 100 expanded steps; sport-specific additional bounds |
| Existing-workout scheduling batch | 1–20 ID/date pairs; not atomic |
| FIT archive download | Exactly one FIT in a bounded ZIP; 16 MiB compressed/uncompressed |
| FIT decoding | At most 100,000 messages / 50,000 recording rows |
| Power best efforts | 5/30/60/300/1,200 seconds, contiguous approximately 1 Hz samples |
| HR/speed drift | At least 600 fully paired contiguous seconds; equal-time halves |
| Write draft | 30-minute expiry; stable 8–128 character idempotency key |
| Journal | At most 1,000 intents / 16 MiB; refuses new entries when full |
| Remote requests | 3 MiB MCP body; 16 KiB OAuth body; activity uploads at most 2 MiB decoded |

Exact argument bounds are queryable via the installed tools. See [account writes](../guides/account-writes.md) for validation and unknown-outcome handling. The durable journal supports duplicate protection, not an atomic transaction across Garmin calls.

## Runtime behavior

Reads use isolated workers, deadlines, a bounded 120-second cache and at most one retry for transient network errors. Authentication/rate-limit failures are not retried. Mutations have no application-level blind retries; an uncertain result requires investigation. TLS verification remains enabled and MCP stdout belongs to the protocol. Returned labels/free text are untrusted data, never instructions.
