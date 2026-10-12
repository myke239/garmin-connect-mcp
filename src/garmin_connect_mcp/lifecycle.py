"""Template lifecycle helpers preserve complete content and detect stale targets."""
import copy
import hashlib
import json
from .data import validate_id
from .writes import validate_workout


def fingerprint(raw):
    return hashlib.sha256(json.dumps(raw, sort_keys=True, allow_nan=False).encode()).hexdigest()


def clone(backend, workout_id, workout_name):
    validate_id(workout_id)
    if not isinstance(workout_name, str) or not 1 <= len(workout_name.strip()) <= 200:
        raise ValueError('Provide a new workout name')
    original = backend.fresh_call('get_workout_by_id', workout_id)
    if not isinstance(original, dict):
        raise ValueError('Unsupported workout template')
    # Keep the executable schema only. Server-owned IDs/owner/access/version data
    # are not valid creation inputs, including nested step/segment IDs.
    allowed = {'workoutName','description','sportType','workoutSegments','estimatedDurationInSecs',
        'estimatedDistanceInMeters','poolLength','poolLengthUnit'}
    payload = {key:copy.deepcopy(value) for key,value in original.items() if key in allowed}
    def strip(value):
        if isinstance(value,dict):
            for key in ('workoutId','workoutSegmentId','stepId','ownerId','author','createdDate','updatedDate'):
                value.pop(key,None)
            for child in value.values(): strip(child)
        elif isinstance(value,list):
            for child in value: strip(child)
    strip(payload)
    payload['workoutName'] = workout_name.strip()
    validate_workout(payload)
    return {'workout_json':payload,'source_workout_id':workout_id,
        'source_content_sha256':fingerprint(original), 'validation_only':True,'garmin_request_sent':False}


def target(backend, workout_id):
    validate_id(workout_id)
    raw = backend.fresh_call('get_workout_by_id',workout_id)
    if not isinstance(raw,dict):
        raise ValueError('Unsupported workout template')
    return {'workout_id':workout_id,'expected_name':raw.get('workoutName'), 'expected_content_sha256':fingerprint(raw),
        'warning':'Deleting a template can remove associated calendar entries; no automatic restoration.'}
