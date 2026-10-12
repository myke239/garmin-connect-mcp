---
name: browse-garmin-exercises
description: Browse Garmin's SDK exercise catalog, search movement names, resolve exact category/exercise identifiers and equipment variants, or check catalog coverage before building workouts.
---

Use the Garmin Connect MCP tool `find_garmin_exercises` for search and standalone
catalog browsing. It is read-only and makes no Garmin account request.
`list_workout_templates` lists saved user workouts, not the exercise catalog.

## First call

For a movement, call `find_garmin_exercises` with:

```json
{"term":"standing calf raises","limit":20,"start":0}
```

For catalog browsing or checking its size, use an empty term:

```json
{"term":"","limit":50,"start":0}
```

`total_matches` counts the current search/filter, not the page size. An unfiltered
empty term reports the full snapshot count. Read it rather than hardcoding a
count that may change with the SDK. Read `source`, `sdk_version` and `coverage`.

## Pagination and selection

Return a useful first page or search result immediately; fetch the whole catalog
only when the task requires it. Repeat the same term, category and limit, setting
`start` to the returned `next_start`. Stop when `next_start` is null, including
when the last page is full. Limits are 1–50; optional `category` is an exact SDK
category such as `SQUAT`. Get category values from
`get_garmin_workout_schema(sport="strength_training")`. On a call error or
pagination that fails to advance, stop and report partial coverage.

Names tolerate plurals, spaces, hyphens and underscores. Inspect `exact_matches`,
`match_status` and `selection_required`; preserve returned category/exercise pairs
verbatim. Partial results and equipment variants are candidates, not substitutes.
Generic Bulgarian split squats require equipment selection; leg press resolves
to SQUAT / LEG_PRESS. Never guess a missing exercise identifier.

`not_found` means absent from the pinned SDK picker snapshot, not necessarily
absent from Garmin. Try the actual movement's spelling or read a known-good saved
workout with `get_workout_template`, without changing the requested movement.
If unresolved, state the limitation and stop dependent workout creation.

For requested strength construction, pass the selected pair to
`build_garmin_strength_step`; use `get_garmin_workout_schema` for sport and step
conventions. Browsing does not authorize saving or scheduling a workout.

If the tool is missing from the agent's available tools, explain that an updated
Garmin Connect connection/tool list is needed. Do not infer that the installed
server lacks browsing from a stale client tool list.

## Yoga pose lookup

Use `find_garmin_exercises(category="POSE", term=...)` to search the 85 verified
Garmin yoga identifiers. Empty term browses; follow next_start for all pages.
Return exact exercise values; labels are enum-derived, not official translations.
Do not reinterpret a Sanskrit/common name without a verified mapping or user
selection. For selected poses use `build_garmin_yoga_step` with whole hold seconds
and sequence order, then the create-schedule-workouts workflow. Do not pass POSE
to the strength builder or claim watch animations.
