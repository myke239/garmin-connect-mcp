"""SDK-backed workout metadata and exact exercise selection; never account writes."""
import math
import re
import unicodedata
from importlib.metadata import version

from .writes import WriteInputError


def normalize(value):
    text=unicodedata.normalize("NFKD",value).casefold()
    text="".join(ch for ch in text if not unicodedata.combining(ch))
    words=re.findall(r"[a-z0-9]+",text)
    def singular(word):
        if word.endswith("sses"): return word[:-2]
        if len(word)>3 and word.endswith("s") and not word.endswith("ss"): return word[:-1]
        return word
    return " ".join(singular(word) for word in words)


def exercises(term="",limit=20,start=0,category=None):
    from garminconnect.exercises import EXERCISES,CATEGORIES
    if (not isinstance(term,str) or len(term)>100 or isinstance(limit,bool) or not isinstance(limit,int)
            or not 1<=limit<=50 or isinstance(start,bool) or not isinstance(start,int) or not 0<=start<=10000):
        raise ValueError("Invalid exercise search")
    if category is not None and category not in CATEGORIES: raise ValueError("Unknown catalog category")
    needle=normalize(term)
    if term.strip() and not needle: raise ValueError("Use searchable letters or digits")
    def exact(row):
        return bool(needle) and needle in {normalize(row["name"]),normalize(row["exercise"]),
                                          normalize(row["category"]+"/"+row["exercise"])}
    rows=[row for row in EXERCISES if (category is None or row["category"]==category)
          and all(token in normalize(row["name"]+" "+row["category"]+" "+row["exercise"]).split() for token in needle.split())]
    rows.sort(key=lambda row:(not exact(row),row["name"].casefold(),row["category"],row["exercise"]))
    exact_rows=[row for row in rows if exact(row)]
    page=rows[start:start+limit]
    return {"exercises":page,"exact_matches":exact_rows[:50],"total_matches":len(rows),
        "next_start":start+len(page) if start+len(page)<len(rows) else None,"truncated":start+len(page)<len(rows),
        "match_status":"exact" if exact_rows else "variants_or_partial" if rows else "not_found",
        "selection_required":not bool(exact_rows) or len(exact_rows)>1,
        "source":"pinned SDK snapshot of Garmin Connect's exercise picker","sdk_version":version("garminconnect"),
        "coverage":"Not a live Garmin picker query; absence here does not establish that Garmin globally lacks the movement.",
        "guidance":"Use exact category/exercise values. Equipment-specific variants are separate choices. Never replace an unresolved movement with a parent category or related exercise without user selection."}


def strength_step(category,exercise,reps,step_order,weight_kg=None):
    from garminconnect.exercises import EXERCISES
    from garminconnect.workout import create_strength_exercise_step
    if not any(row["category"]==category and row["exercise"]==exercise for row in EXERCISES):
        raise WriteInputError("build_garmin_strength_step","Choose an exact category/exercise pair from find_garmin_exercises; unsupported movements cannot be substituted.")
    for name,value,maximum in (("reps",reps,1000),("step_order",step_order,100)):
        if isinstance(value,bool) or not isinstance(value,int) or not 1<=value<=maximum:
            raise WriteInputError("build_garmin_strength_step",name+" must be a positive integer within the published bound.")
    if weight_kg is not None and (isinstance(weight_kg,bool) or not isinstance(weight_kg,(int,float))
            or not math.isfinite(weight_kg) or not 0<=weight_kg<=1000):
        raise WriteInputError("build_garmin_strength_step","weight_kg must be finite, between 0 and 1000 kg, or omitted for no encoded load target.")
    step=create_strength_exercise_step(category=category,exercise_name=exercise,reps=reps,
        step_order=step_order,weight_kg=weight_kg).model_dump(exclude_none=True,mode="json")
    return {"step":step,"sportType":{"sportTypeId":5,"sportTypeKey":"strength_training","displayOrder":5},
        "source":"pinned Garmin SDK create_strength_exercise_step","sdk_version":version("garminconnect"),
        "garmin_request_sent":False,"guidance":"This builds JSON only. Assemble the user's selected workout, prepare it, review/authorize the exact preview, then commit. Load targets use grams in weightValue with the SDK kilogram unit/factor; recorded activity-set weights have separate unverified raw units."}


def workout_schema(sport):
    from garminconnect import workout
    models={"running":workout.RunningWorkout,"cycling":workout.CyclingWorkout,
        "swimming":workout.SwimmingWorkout,"walking":workout.WalkingWorkout,
        "hiking":workout.HikingWorkout,"strength_training":workout.StrengthWorkout}
    if sport not in models and sport!="yoga": raise ValueError("Unsupported workout sport")
    sport_type=({"sportTypeId":workout.SportType.YOGA,"sportTypeKey":"yoga","displayOrder":7}
                if sport=="yoga" else models[sport].model_fields["sportType"].default_factory())
    example=(workout.create_strength_exercise_step("SQUAT",1,1,"SQUAT") if sport=="strength_training"
             else workout.create_interval_step(300,1) if sport=="yoga"
             else workout.create_distance_interval_step(1000,1)).model_dump(exclude_none=True,mode="json")
    result={"sportType":sport_type,"reps_condition":{"conditionTypeId":10,"conditionTypeKey":"reps","displayOrder":10},
        "example_step":example,"example_only":True,"sdk_version":version("garminconnect"),
        "required_workout_fields":["workoutName","sportType","workoutSegments"],
        "guidance":"Get actual exercise enum pairs from find_garmin_exercises and build exact reps/load steps with build_garmin_strength_step. Example quantities are illustrative, not the user's routine. Scheduling uses workout_id and date_str. Never substitute unavailable movements."}
    if sport=="yoga":
        result["example_workout"]={"workoutName":"Example timed yoga session", "sportType":sport_type,
            "estimatedDurationInSecs":300,"workoutSegments":[{"segmentOrder":1,"sportType":sport_type,"workoutSteps":[example]}]}
        result["example_limit"]="A timed untargeted yoga session, not a pose sequence. Change name and seconds to the requested session; estimatedDurationInSecs and endConditionValue must agree. No poses are encoded in a description. Copy a verified yoga template for pose-specific fields; strength/stretch catalog entries do not establish yoga pose IDs."
        result["guidance"]="Yoga can be created and scheduled with create_workout or create_training_calendar. Use the complete example_workout with requested name/duration, prepare, authorize, commit and verify. Schedule saved workout_id with date_str. Example is not authorization to save."
    if sport=="strength_training":
        from garminconnect.exercises import CATEGORIES
        result["exercise_categories"]=CATEGORIES
        result["load_target_units"]={"input":"weight_kg","weightValue":"grams",
            "weightUnit":workout.WEIGHT_UNIT_KILOGRAM,"conversion":"weightValue = weight_kg * 1000"}
    elif sport!="yoga":
        result["example_limit"]="Illustrates basic time/distance step fields; use a real sport-specific template for swimming strokes/equipment and other advanced fields."
    return result
