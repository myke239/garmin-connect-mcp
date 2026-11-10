# Garmin Connect MCP 0.21.0

Creates executable strength sets, timed holds and running intervals with repeat
groups, configurable rests and transitions. Adds familiar mile pace/distance
inputs and corrects Connect pace ordering and planned strength load units.

Existing template updates preserve identity, read back the saved program and
skip already-applied changes. Interrupted updates can be reconciled against the
protected per-workout journal. Quality warnings flag contradictory workout notes.

Also includes daily/weekly health review skills and durable review monitoring.
Host scheduling and outbound notification delivery remain separate integrations.

**Windows: download GarminConnectSetup.exe and follow the guided installer.**
Linux/Windows portable archives are also provided. Existing credentials and write
policies remain separate from the application.

[Installation guide](https://github.com/myke239/garmin-connect-mcp/blob/main/docs/getting-started/installation.md)

Downloads are **unsigned**; a verified publisher is not claimed. Publication
requires offline tests, isolated installation and MCP checks. Garmin Connect
display and watch execution are separate acceptance checks: the user's reported
pace/load display observations inform this release, but Instinct 2 out-of-range
pace vibration and swimming pace display have not been verified here. Existing
workouts are not automatically migrated or rescaled.

The public executable excludes Garmin's separately licensed FIT SDK. Optional
FIT support remains available through the advanced `fit-setup` command.
