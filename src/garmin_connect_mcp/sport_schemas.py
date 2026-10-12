"""Workout sport registry; IDs checked against Garmin workout metadata 2026-10-12."""
from typing import Literal
SportKey=Literal['running','cycling','other','swimming','strength_training','cardio_training','yoga','pilates','hiit','multi_sport','mobility','rucking','walking','hiking']
SPORT_IDS={'running':1,'cycling':2,'other':3,'swimming':4,'strength_training':5,'cardio_training':6,
           'yoga':7,'pilates':8,'hiit':9,'multi_sport':10,'mobility':11,'rucking':13}
WORKOUT_TYPES_ENDPOINT='/workout-service/workout/types'
# Catalog entries that are system events or obsolete combined types are not exercise logs.
NON_EXERCISE_TYPES={'all','safety','assistance','incident_detected','fall_detected','steps',
                   'transition_v2','swimToBikeTransition_v2','bikeToRunTransition_v2','runToBikeTransition_v2'}

def manual_type_supported(row):
    return not row.get('restricted') and not row.get('isHidden') and row.get('typeKey') not in NON_EXERCISE_TYPES

def sport_enum(sport):
    if sport not in SPORT_IDS:
        from .writes import WriteInputError
        raise WriteInputError('build_garmin_workout','Unsupported workout sport; walking/hiking legacy SDK enums fail Garmin sport readback. Choose a listed workout sport only with user selection, or record a completed activity with its exact activity type.')
    return {'sportTypeId':SPORT_IDS[sport],'sportTypeKey':sport,'displayOrder':SPORT_IDS[sport]}

def workout_sports(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get('workoutSportTypes'),list):raise ValueError('Unsupported workout metadata')
    rows=[]
    for row in raw['workoutSportTypes']:
        key=row.get('sportTypeKey'); known=SPORT_IDS.get(key)==row.get('sportTypeId')
        rows.append({**{k:row[k] for k in ('sportTypeId','sportTypeKey','displayOrder') if k in row},
                     'schema_available':known,'creation_supported':known,'calendar_scheduling_supported':known})
    return {'workout_sports':rows[:50],'truncated':len(rows)>50,
            'unsupported_sdk_workout_sports':[{'sport':k,'creation_supported':False,'reason':'SDK legacy workout enum is not in Garmin workout catalog and live readback loses its sport identity. Completed manual activities are supported; do not relabel plans implicitly.'} for k in ('walking','hiking')],
            'guidance':'Workout sports differ from recorded activity types. Use get_garmin_workout_schema and build_garmin_workout. Device execution support varies; queued does not mean downloaded.'}

def build_workout(sport,workout_name,duration_seconds=None,workout_segments=None,description=None):
    import copy
    from garminconnect.workout import create_interval_step
    from .writes import validate,WriteInputError
    if (duration_seconds is None)==(workout_segments is None):
        raise WriteInputError('build_garmin_workout','Supply exactly one of duration_seconds or workout_segments; do not invent session structure.')
    header=sport_enum(sport)
    if duration_seconds is not None:
        if sport=='multi_sport':raise WriteInputError('build_garmin_workout','Multisport requires explicit workout_segments with the selected constituent sports; do not choose sports implicitly.')
        if isinstance(duration_seconds,bool) or not isinstance(duration_seconds,int) or not 1<=duration_seconds<=604800:
            raise WriteInputError('build_garmin_workout','duration_seconds must be a whole number from 1 to 604800 seconds.')
        steps=[create_interval_step(duration_seconds,1).model_dump(mode='json',exclude_none=True)]
        segments=[{'segmentOrder':1,'sportType':header,'workoutSteps':steps}]
    else:segments=copy.deepcopy(workout_segments)
    template={'workoutName':workout_name,'sportType':header,'estimatedDurationInSecs':duration_seconds or 0,'workoutSegments':segments}
    if description is not None:
        if not isinstance(description,str) or len(description)>2000:raise WriteInputError('build_garmin_workout','description is limited to 2000 characters.')
        template['description']=description
    validate('create_workout',{'workout_json':template})
    return {'workout_json':template,'garmin_request_sent':False,
            'guidance':'JSON only; prepare and authorize the exact write, commit and verify. Timed sessions encode no poses, strokes, equipment, load or intensity. Advanced fields require verified templates. Explicit segments use estimated duration 0 (unknown), not a measured duration.'}

def activity_schema(raw,type_key):
    from .write_contracts import contract
    from .writes import WriteInputError
    if not isinstance(raw,list):raise ValueError('Unsupported activity catalog')
    row=next((r for r in raw if r.get('typeKey')==type_key),None)
    if row is None:raise WriteInputError('get_garmin_activity_schema','Choose an exact type_key from list_garmin_activity_types; workout and activity names differ.')
    supported=manual_type_supported(row)
    result={'activity_type':{k:row.get(k) for k in ('typeId','typeKey','parentTypeId','restricted','isHidden')},
        'manual_creation_supported':supported,'workout_schema_sport':type_key if type_key in SPORT_IDS else None,
        'manual_activity_calendar_scheduling_supported':False,
        'guidance':'Recorded activity logs are for completed sessions with actual user-provided values. Never create a future activity to simulate a planned workout. Only workout templates support calendar scheduling. No medical/diving metrics or GPS are fabricated; use a supplied activity file for richer recorded data.'}
    if supported:
        result['write_contract']=contract('create_manual_activity')
        result['write_contract']['parameter_schema']['properties']['type_key']['const']=type_key
        result['creation_limits']='Shared SDK manual log fields only; catalog membership and local validation do not guarantee upstream acceptance for every activity type.'
        result['parameter_template']={'type_key':type_key,'start_datetime':'<actual local YYYY-MM-DDTHH:MM:SS>',
            'time_zone':'<actual IANA timezone>','distance_km':'<actual distance in km; explicit 0 if none>',
            'duration_min':'<actual whole minutes>','activity_name':'<requested name>'}
    else:result['unsupported_reason']='Restricted, hidden, aggregate, transition or safety-event type; cannot create an exercise log through this connector.'
    return result

def build_manual_activity(raw,parameters):
    from .writes import validate,WriteInputError
    p=validate('create_manual_activity',parameters)
    schema=activity_schema(raw,p['type_key'])
    if not schema['manual_creation_supported']:raise WriteInputError('build_garmin_manual_activity',schema['unsupported_reason'])
    return {'parameters':p,'garmin_mutation_sent':False,'catalog_read_required':True,'guidance':schema['guidance']+' Prepare create_manual_activity, authorize the preview, commit and verify the returned activity ID.'}
