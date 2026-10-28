# Strength workout discovery

Call `get_garmin_workout_schema(sport="strength_training")` for the current SDK
header and example. Strength uses sport ID 5 / strength_training; repetitions
use condition ID 10 / reps. The example is illustrative, not a requested workout.

Search each requested movement with `find_garmin_exercises(term, limit, start)`.
Use `exact_matches`, `match_status`, `selection_required` and `next_start`.
Search tolerates plurals, spaces, underscores and hyphens. Partial matches are
discovery candidates, not permission to choose a different movement or equipment.

Known SDK catalog pairs:

| Movement | category | exercise |
|---|---|---|
| Squat | SQUAT | SQUAT |
| Leg press | SQUAT | LEG_PRESS |
| Standing calf raise | CALF_RAISE | STANDING_CALF_RAISE |
| Dumbbell Bulgarian split squat | LUNGE | DUMBBELL_BULGARIAN_SPLIT_SQUAT |
| Barbell Bulgarian split squat | LUNGE | BARBELL_BULGARIAN_SPLIT_SQUAT |

The catalog also has overhead variants. A generic Bulgarian split squat query
requires explicit equipment selection; do not choose dumbbells by default.
Step-downs have no match in the pinned SDK picker snapshot. This does not prove
Garmin lacks the exercise. Retrieve a known-good account template containing the
actual movement or explain the unresolved identifier. Do not substitute step-ups,
lunges or a broad category, and do not fabricate new catalog definitions.

For a single low-level step, call `build_garmin_strength_step` with the exact category/exercise,
integer reps (1–1000), integer step_order (1–100), and optional `weight_kg`.
It returns an ExecutableStepDTO without sending a Garmin request. Planned load
input is kg; the SDK encodes weightValue in grams with its kilogram unit object.
This convention does not establish units for recorded activity exerciseSets;
those remain raw and must be preserved when editing activity sets.

## Declarative authoring

Prefer `build_garmin_strength_workout` for a complete routine. Inputs use
`workout_name`, `exercises` in the requested order, and optional `defaults`:

```json
{
  "workout_name": "Skill and strength",
  "defaults": {
    "rest_between_sets_seconds": 60,
    "rest_between_exercises_seconds": 120
  },
  "exercises": [
    {
      "name": "Wall Handstand Hold",
      "sets": 10,
      "duration_seconds": 20,
      "rest_seconds": 40,
      "include_final_rest": true,
      "notes": "Maintain straight arms and controlled alignment."
    },
    {"name": "Leg press", "sets": 3, "reps": 10},
    {"name": "Standing calf raise", "sets": 3, "reps": 8}
  ]
}
```

Each exercise has a `name` (exact name lookup) or selected `category` and
`exercise` identifiers, sets 1–99, and exactly one of `reps` or
`duration_seconds`. Optional fields: `weight_kg`, `notes`, `rest_seconds`,
`transition_seconds`, `include_final_rest`. Rest/transition values are whole
seconds 0–3600. Defaults are local authoring conventions, not universal training
recommendations; honor prescribed rests and expose defaults in the preview.

The builder creates one `RepeatGroupDTO` per exercise containing the exercise
and timed rest, with `numberOfIterations=sets` and `skipLastRestStep=true`.
The 120-second transition between exercises replaces the final 60-second rest;
it does not follow an extra 60 seconds. No transition follows the final exercise.
An explicitly zero rest omits the rest child; even one set remains a group.

Use time for handstands, L-sits, planks, hollow-body holds and similar isometrics.
For an intentional complete 10-minute 20s/40s block, set `include_final_rest=true`:
ten holds and ten recoveries total 600 seconds. Its final 40 seconds remain part
of the practice block and the next exercise's 120-second transition follows.
Without final recovery, the block totals 560 seconds. Do not add this flag to
ordinary strength blocks by default.

Unique exact display names take priority over shared bare enum names. Partial
or equipment-specific matches are not substitutions. Unresolved rep-based
movements stop with a resolution error. Unresolved timed names produce a generic
timed step without a catalog exercise, retaining the real movement and notes
in `description`; disclose the warning that Garmin may show a generic label.
Catalog absence means absent from the pinned snapshot, not proven absent from
all Garmin versions. Generic timed fallback does not support a load target.

The output includes `workout_json`, a per-exercise preview, warnings and
`duration_estimate`. Programmed time includes only the rests/holds that execute.
Rep-based or distance-based work has unknown duration: `total_seconds=null`
and the Garmin estimate is 0 (unknown). Do not invent a rep cadence or describe
programmed hold duration as measured successful performance.

Review the full JSON for loads/targets and the preview for set/rest/transition
semantics. Keep the normal prepare → authorized commit → recursive readback
workflow in the main skill. Use `date_str` and the verified `workout_id`.

Validation: a temporary four-step strength workout with squat, leg press,
standing calf raise and dumbbell Bulgarian split squat was accepted by Garmin,
read back with matching identifiers and removed. This verifies those exact pairs
and header/reps conventions, not every catalog entry or a user's complete routine.
