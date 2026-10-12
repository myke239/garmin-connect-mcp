# Write audit — 2026-10-11–12

This audit covers all 16 MCP write operations against python-garminconnect
0.3.17, both through intercepted SDK transport tests and explicitly authorized
live-account tests. Synthetic resources were used; existing user workouts were
preserved. Live tests are never run by default tests or CI.

| MCP operation | Live evidence |
| --- | --- |
| create_workout | Created test template; name/content read back |
| update_workout | Renamed test template; read back |
| schedule_workout | Test entry found in calendar on requested date |
| unschedule_workout | Test entry absent on fresh calendar read |
| create_training_calendar | Test template created and calendar entry read back |
| send_workout_to_device | Queue accepted; physical download not verified |
| create_manual_activity | Current-date walking activity created/read back; historical strength/zero-distance variant returned upstream error and remained unknown |
| set_activity_name | Test activity name read back |
| set_activity_description | Test description read back |
| set_activity_type | Test type changed using actual catalog tuple; read back |
| replace_strength_sets | One synthetic set written to test activity; full sets read back |
| upload_activity_file | GPX, TCX and FIT recordings imported and reconciled by timestamp/duration/distance |
| add_weight | Synthetic historical weight read back |
| add_body_composition | Historical composition import read back after a delay |
| add_hydration | Synthetic historical delta read back; reversed to baseline total |
| add_blood_pressure | Synthetic historical measurement read back |

An additional test verified the optional-pulse path. A final live check verified
that duplicate scheduling returns a preflight rejection before any mutation;
the final test schedule/template were removed and checked.

All known test workouts, calendar entries, activities, weight/composition and
blood-pressure records were removed and checked. Hydration total returned to
zero; last-entry metadata may remain. A device queue message may persist until
device sync; its test workout was deleted, and no download can be claimed.
At-most-once journal entries are retained locally, encrypted, rather than erased.
No account identifiers or measurement values are published in this report.

## Findings and guards

- JSON names and SDK argument names differ. The operation schema tool provides
  exact required/optional fields and units to every MCP client, including ChatGPT.
- Every operation now gets local schema/type/range validation and safe input
  errors. Invalid payload values and upstream exception messages are not echoed.
- Existing targets, device membership and activity type tuples are read before
  mutation. Duplicate known calendar entries and foreign exercise-set IDs reject
  before writing. Rejected results explicitly say no mutation was attempted.
- Workout enum pairs and nested steps are checked. Complete replacements bind
  the body ID to the requested target. Manual local time rejects DST ambiguity.
- Composition limits follow FIT integer scales and epoch bounds. Weight response
  units differ from write units. Hydration local dates must agree.
- Uploads check size, FIT CRC/decoded activity messages and XML track timing.
  Partial/failed import response bodies never count as completed writes.
- Import acceptance may precede visibility and omit IDs; agents must reconcile
  rather than recreate. Fresh verification reads avoid the server's read cache.
- SDK 0.3.17 automatically retries a request after HTTP 401. A per-call transport
  guard blocks replays of account mutations while allowing reads/token refresh.
- Durable status reads do not require a commit. Unknown/in-progress outcomes
  retain the no-retry rule; validation/preflight rejections are distinguished.
- Authenticated public HTTP discovery/schema/calendar checks passed and a
  temporary read grant correctly rejected writes; that audit connection was removed.
  Terminal consent now displays actual scopes and labels write grants explicitly.

## SDK-only mutation inventory

Source inspection also covered methods outside the MCP allowlist. They remain
unavailable to downstream agents; rejection is tested. This is intentional,
not a claim that every SDK endpoint has been live-tested on this account.

| SDK methods | Disposition |
| --- | --- |
| upload_running/cycling/swimming/walking/hiking/strength_workout | Typed wrappers over upload_workout; MCP uses complete validated JSON |
| create_manual_activity_from_json | Internal fixed SDK route; arbitrary JSON operation unavailable |
| import_activity | Alternate import wrapper; bounded upload_activity_file is the MCP route |
| add_weigh_in_with_timestamps | Alternate local/GMT arguments; MCP uses one explicit offset timestamp |
| delete_activity, delete_workout, delete_weigh_in, delete_blood_pressure | Used only by owner-authorized local test cleanup; not remote operations |
| delete_weigh_ins | Bulk deletion unavailable; never used for live test cleanup |
| create_gear, set_gear_default, add_gear_to_activity, remove_gear_from_activity | Not exposed; no gear or user defaults changed |
| request_reload | Maintenance operation unavailable |
| update_menstrual_daily_log/calendar/settings, init_menstrual_cycle_setup, confirm_menstrual_period_start | Not exposed; no reproductive-health settings changed |
| connectwebproxy, query_garmin_graphql | Arbitrary request surfaces unavailable |

This account provides evidence for the listed test paths, not every device,
activity type, date, target, exercise, measurement field or file the SDK accepts.
Unofficial endpoints may change. Physical-device sync remains outside automated
verification.

## Repeating the audit

From a source checkout with the installed environment and saved Garmin session:

```powershell
& 'D:\developer\garmin-connect-mcp\.venv313\Scripts\python.exe' 'D:\developer\garmin-connect-mcp\scripts\live_write_audit.py'
```

The default performs no writes. Only an owner who explicitly authorizes synthetic
account changes should use `--run`. It writes encrypted run evidence under
`work/live-write-audit` and uses separate stable journal intents. `--cleanup`
only reconciles/removes recorded test resources. Do not reuse a completed run to
recreate deleted resources, reset unknown journal entries, or guess cleanup IDs.
Imports may require later reconciliation and another cleanup check. Preserve
private run evidence until reconciliation is complete.
