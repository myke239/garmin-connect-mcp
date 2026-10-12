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

Once resolved, call `build_garmin_strength_step` with the exact category/exercise,
integer reps (1–1000), integer step_order (1–100), and optional `weight_kg`.
It returns an ExecutableStepDTO without sending a Garmin request. Planned load
input is kg; the SDK encodes weightValue in grams with its kilogram unit object.
This convention does not establish units for recorded activity exerciseSets;
those remain raw and must be preserved when editing activity sets.

Assemble the complete template using the schema header and returned steps.
Specify requested rests, sets, targets and repeats explicitly; do not infer them
from descriptions. Keep the normal prepare → authorized commit → readback workflow
in the main skill. Schedule only a verified saved template after every requested
movement is resolved. Use date_str and the verified workout_id.

Validation: a temporary four-step strength workout with squat, leg press,
standing calf raise and dumbbell Bulgarian split squat was accepted by Garmin,
read back with matching identifiers and removed. This verifies those exact pairs
and header/reps conventions, not every catalog entry or a user's complete routine.
