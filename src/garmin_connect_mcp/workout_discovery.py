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
    from .sport_schemas import sport_enum
    if sport in {"walking","hiking"}:
        return {"sport":sport,"creation_supported":False,"calendar_scheduling_supported":False,"guidance":"Garmin does not advertise this workout sport and live SDK legacy-enum templates lose their sport identity. Completed activities remain available through get_garmin_activity_schema. Do not silently substitute running or other; use Garmin planning directly if needed."}
    header=sport_enum(sport)
    step=(workout.create_strength_exercise_step("SQUAT",1,1,"SQUAT") if sport=="strength_training"
          else workout.create_interval_step(300,1)).model_dump(exclude_none=True,mode="json")
    template={"workoutName":"Example "+sport+" session","sportType":header,
        "estimatedDurationInSecs":0 if sport=="strength_training" else 300,
        "workoutSegments":[{"segmentOrder":1,"sportType":header,"workoutSteps":[step]}]}
    limit="Basic timed untargeted session only; detailed exercises, equipment, strokes, intensity and ruck pack load need verified sport-specific fields. A description does not encode these."
    if sport=="multi_sport":
        template["estimatedDurationInSecs"]=600
        template["workoutSegments"]=[{"segmentOrder":i,"sportType":sport_enum(k),"workoutSteps":[workout.create_interval_step(300,i).model_dump(exclude_none=True,mode="json")]} for i,k in enumerate(("running","cycling"),1)]
        limit="Illustrative run-bike segments, not the user selected sports. Supply explicit requested constituent sports/segments to build_garmin_workout; never choose these implicitly."
    json_schema=workout.BaseWorkout.model_json_schema()
    json_schema["properties"]["sportType"]={"type":"object","required":["sportTypeId","sportTypeKey"],"properties":{"sportTypeId":{"const":header["sportTypeId"]},"sportTypeKey":{"const":sport}},"additionalProperties":True}
    result={"json_schema":json_schema,"sportType":header,"reps_condition":{"conditionTypeId":10,"conditionTypeKey":"reps","displayOrder":10},
        "example_step":step,"example_workout":template,"example_only":True,"sdk_version":version("garminconnect"),
        "required_workout_fields":["workoutName","sportType","estimatedDurationInSecs","workoutSegments"],
        "example_limit":limit,"guidance":"Use the complete example_workout or build_garmin_workout for the user's requested sport/name/duration. Examples are not authorization to save. Prepare create_workout, authorize the preview, commit and verify. Schedule workout_id with date_str, or use create_training_calendar. Recorded activity types are separate; no automatic substitution with other sports."}
    if sport=="strength_training":
        from garminconnect.exercises import CATEGORIES
        result["exercise_categories"]=CATEGORIES
        result["example_limit"]="One illustrative squat repetition, not the user's routine; estimated duration 0 means unknown. Resolve exact catalog pairs and build requested reps/load steps with build_garmin_strength_step."
        result["load_target_units"]={"input":"weight_kg","weightValue":"grams","weightUnit":workout.WEIGHT_UNIT_KILOGRAM,"conversion":"weightValue = weight_kg * 1000"}
    return result
