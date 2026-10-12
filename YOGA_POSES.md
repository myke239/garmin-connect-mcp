# Verified Garmin yoga poses

Verified on **2026-10-12** with **python-garminconnect 0.3.17**.

Garmin's [Yoga.json catalog](https://connect.garmin.com/web-data/exercises/Yoga.json)
contains 202 exercise entries across 11 categories. The **85 entries in POSE**
are listed below. Other categories in Yoga.json contain movements, core exercises
and related exercises; they are not included in this pose-only list.

## Verification and limits

The [SDK model source](https://github.com/cyberjunky/python-garminconnect/blob/master/garminconnect/workout.py) supports generic workout DTOs with extra fields. The test used the installed pinned version, rather than treating a model validation pass alone as Garmin acceptance.

Every listed identifier passed native SDK BaseWorkout/ExecutableStep JSON
round-trip validation and live Garmin acceptance. Four synthetic yoga templates
(25/25/25/10 steps) used sport 7/yoga, category POSE, exact exerciseName, a timed
30-second duration, no target and unique step orders. Each was uploaded through
SDK upload_workout and read back through get_workout_by_id; exact category,
exerciseName and duration matched for all 85 steps. All four templates were
deleted, subsequent lookups returned NOT_FOUND, and the complete paginated
workout library contained no matching audit templates. No calendar entries,
recorded activities or physical-device downloads were created for this audit.

This proves availability in the catalog and acceptance in timed yoga workout
steps on the tested account/date. It does not prove pose animation or execution
on every watch, every timing/target variant, or clinical suitability. Garmin's
[animated-workout support guidance](https://support.garmin.com/en-CA/?faq=IPD6X8JSLBAUQOXvz7zBO6&productID=730659&tab=topics)
distinguishes premade animated workouts from custom workouts; catalog presence
and API acceptance alone do not establish animation availability.

Version 0.7.0 exposes all verified POSE identifiers through catalog discovery,
a timed step builder, and guarded create/update/calendar writes. During release
testing every pose passed guarded creation and exact Garmin readback in four
batches; update, scheduling and unscheduling also passed. All fixtures were
removed. Version 0.6.0 had rejected POSE against its strength-only catalog.

## Exact identifiers

Use **category: POSE** for every row and preserve exerciseName exactly.

| # | exerciseName |
|---:|---|
| 1 | `ALL_FOURS` |
| 2 | `ANKLE_TO_KNEE` |
| 3 | `BABY_COBRA` |
| 4 | `BOAT` |
| 5 | `BOUND_ANGLE` |
| 6 | `BOUND_SEATED_SINGLE_LEG_FORWARD_BEND` |
| 7 | `BOW` |
| 8 | `BOWED_HALF_MOON` |
| 9 | `BRIDGE` |
| 10 | `CAT` |
| 11 | `CHAIR` |
| 12 | `CHILDS` |
| 13 | `CORPSE` |
| 14 | `COW_FACE` |
| 15 | `COW` |
| 16 | `DEVOTIONAL_WARRIOR` |
| 17 | `DOLPHIN_PLANK` |
| 18 | `DOLPHIN` |
| 19 | `DOWN_DOG_KNEE_TO_NOSE` |
| 20 | `DOWN_DOG_SPLIT` |
| 21 | `DOWN_DOG_SPLIT_OPEN_HIP_BENT_KNEE` |
| 22 | `DOWNWARD_FACING_DOG` |
| 23 | `EAGLE` |
| 24 | `EASY_SEATED` |
| 25 | `EXTENDED_PUPPY` |
| 26 | `EXTENDED_SIDE_ANGLE` |
| 27 | `FISH` |
| 28 | `FOUR_LIMBED_STAFF` |
| 29 | `FULL_SPLIT` |
| 30 | `GATE` |
| 31 | `HALF_CHAIR_HALF_ANKLE_TO_KNEE` |
| 32 | `HALF_MOON` |
| 33 | `HEAD_TO_KNEE` |
| 34 | `HERON` |
| 35 | `HEROS` |
| 36 | `HIGH_LUNGE` |
| 37 | `KNEES_CHEST_CHIN` |
| 38 | `LIZARD` |
| 39 | `LOCUST` |
| 40 | `LOW_LUNGE` |
| 41 | `LOW_LUNGE_TWIST` |
| 42 | `LOW_LUNGE_WITH_KNEE_DOWN` |
| 43 | `MERMAID` |
| 44 | `MOUNTAIN` |
| 45 | `ONE_LEGGED_DOWNWARD_FACING_POSE_OPEN_HIP_BENT_KNEE` |
| 46 | `ONE_LEGGED_PIGEON` |
| 47 | `PEACEFUL_WARRIOR` |
| 48 | `PLOW` |
| 49 | `RECLINED_HAND_TO_FOOT` |
| 50 | `REVOLVED_HALF_MOON` |
| 51 | `REVOLVED_HEAD_TO_KNEE` |
| 52 | `REVOLVED_TRIANGLE` |
| 53 | `RUNNERS_LUNGE` |
| 54 | `SEATED_EASY_SIDE_BEND` |
| 55 | `SEATED_EASY_TWIST` |
| 56 | `SEATED_LONG_LEG_FORWARD_BEND` |
| 57 | `SEATED_WIDE_LEG_FORWARD_BEND` |
| 58 | `SHOULDER_STAND` |
| 59 | `SIDE_BOAT` |
| 60 | `SPHINX` |
| 61 | `SQUAT_OPEN_ARM_TWIST` |
| 62 | `SQUAT_PALM_PRESS` |
| 63 | `STAFF` |
| 64 | `STANDING_ARMS_UP` |
| 65 | `STANDING_FORWARD_BEND_HALFWAY_UP` |
| 66 | `STANDING_FORWARD_BEND` |
| 67 | `STANDING_SIDE_OPENER` |
| 68 | `STANDING_SINGLE_LEG_FORWARD_BEND` |
| 69 | `STANDING_SPLIT` |
| 70 | `STANDING_WIDE_LEG_FORWARD_BEND` |
| 71 | `STANDING_WIDE_LEG_FORWARD_BEND_WITH_TWIST` |
| 72 | `SUPINE_SPINAL_TWIST` |
| 73 | `TABLE_TOP` |
| 74 | `THREAD_THE_NEEDLE` |
| 75 | `THUNDERBOLT` |
| 76 | `THUNDERBOLT_POSE_BOTH_SIDES_ARM_STRETCH` |
| 77 | `TREE` |
| 78 | `TRIANGLE` |
| 79 | `UP_DOG` |
| 80 | `UPWARD_FACING_PLANK` |
| 81 | `WARRIOR_ONE` |
| 82 | `WARRIOR_THREE` |
| 83 | `WARRIOR_TWO` |
| 84 | `WHEEL` |
| 85 | `WIDE_SIDE_LUNGE` |

Catalog SHA-256: `548b79660774cae75ff55f1eb1cef220bd69ea2492bd23dcc4145e5daa7f19b8`.

## MCP 0.7.0 support

The connector now exposes these 85 identifiers through `find_garmin_exercises(category="POSE")` and builds timed steps with `build_garmin_yoga_step`. Assemble explicit yoga segments with `build_garmin_workout`, then use the existing preview/commit and calendar workflow. Unknown identifiers, other segment sports, reps/targets/loads and fractional hold seconds are rejected locally. The earlier guard limitation describes version 0.6.0 only.
