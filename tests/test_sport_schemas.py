import copy
import pytest
from garmin_connect_mcp.sport_schemas import SPORT_IDS,build_workout,activity_schema,build_manual_activity,workout_sports,manual_type_supported
from garmin_connect_mcp.workout_discovery import workout_schema
from garmin_connect_mcp.writes import validate,preflight
from garmin_connect_mcp.runtime import RequestError

@pytest.mark.parametrize('sport',SPORT_IDS)
def test_each_complete_workout_schema_validates_and_can_schedule(sport):
    payload=workout_schema(sport)['example_workout']
    assert payload['sportType']['sportTypeId']==SPORT_IDS[sport]
    from jsonschema import Draft202012Validator
    Draft202012Validator(workout_schema(sport)['json_schema']).validate(payload)
    validate('create_workout',{'workout_json':payload})
    validate('create_training_calendar',{'workouts':[{'date':'2026-11-01','workout':payload}]})
    if sport!='multi_sport':
        built=build_workout(sport,'Requested session',duration_seconds=1800)['workout_json']
        assert built['estimatedDurationInSecs']==built['workoutSegments'][0]['workoutSteps'][0]['endConditionValue']==1800
    else:
        built=build_workout(sport,'Requested multisport',workout_segments=payload['workoutSegments'])['workout_json']
        assert len(built['workoutSegments'])==2

@pytest.mark.parametrize('args',[{}, {'duration_seconds':0},{'duration_seconds':True}, {'duration_seconds':1.5},{'duration_seconds':604801}, {'duration_seconds':300,'workout_segments':[]}, {'workout_segments':[]}])
def test_builder_rejects_missing_conflicting_or_invalid_structure(args):
    with pytest.raises(ValueError):build_workout('running','Example',**args)

def test_builder_does_not_choose_multisport_segments_or_mutate_input():
    with pytest.raises(ValueError):build_workout('multi_sport','Example',duration_seconds=300)
    segments=workout_schema('multi_sport')['example_workout']['workoutSegments'];original=copy.deepcopy(segments)
    result=build_workout('multi_sport','Selected sports',workout_segments=segments)
    result['workout_json']['workoutSegments'][0]['sportType']['sportTypeKey']='other'
    assert segments==original

def test_live_sport_discovery_distinguishes_unknown_schema():
    result=workout_sports({'workoutSportTypes':[{'sportTypeKey':'mobility','sportTypeId':11},{'sportTypeKey':'new_sport','sportTypeId':99}]})
    assert result['workout_sports'][0]['schema_available']
    assert not result['workout_sports'][1]['creation_supported']

@pytest.mark.parametrize('sport',['pilates','cardio_training','hiit','mobility','rucking','other'])
def test_sport_id_and_segment_guards(sport):
    payload=workout_schema(sport)['example_workout'];wrong=copy.deepcopy(payload);wrong['sportType']['sportTypeId']=99
    with pytest.raises(ValueError):validate('create_workout',{'workout_json':wrong})
    wrong=copy.deepcopy(payload);wrong['workoutSegments'][0]['sportType']={'sportTypeId':1,'sportTypeKey':'running'}
    with pytest.raises(ValueError):validate('create_workout',{'workout_json':wrong})

CATALOG=[{'typeKey':'tennis_v2','typeId':1,'parentTypeId':0}, {'typeKey':'all','typeId':2,'parentTypeId':0}, {'typeKey':'safety','typeId':3,'parentTypeId':0}, {'typeKey':'obsolete','restricted':True}, {'typeKey':'hidden','isHidden':True}]
PARAMETERS={'type_key':'tennis_v2','activity_name':'Actual tennis','start_datetime':'2026-10-11T12:00:00','time_zone':'America/Los_Angeles','distance_km':0,'duration_min':30}

def test_manual_activity_schema_and_builder_use_exact_live_type():
    schema=activity_schema(CATALOG,'tennis_v2')
    assert schema['manual_creation_supported'] and not schema['manual_activity_calendar_scheduling_supported']
    assert schema['parameter_template']['type_key']=='tennis_v2'
    assert build_manual_activity(CATALOG,PARAMETERS)['parameters']=={**PARAMETERS,'start_datetime':'2026-10-11T12:00:00.000'}
    with pytest.raises(ValueError):build_manual_activity(CATALOG,{**PARAMETERS,'type_key':'tennis'})

@pytest.mark.parametrize('key',['all','safety','obsolete','hidden'])
def test_system_restricted_types_cannot_bypass_builder_at_commit(key):
    assert not activity_schema(CATALOG,key)['manual_creation_supported']
    with pytest.raises(ValueError):build_manual_activity(CATALOG,{**PARAMETERS,'type_key':key})
    class Client:
        def get_activity_types(self):return CATALOG
    with pytest.raises(RequestError,match='ACTIVITY_TYPE_MISMATCH'):preflight(Client(),'create_manual_activity',{**PARAMETERS,'type_key':key})


def test_multisport_duplicate_step_orders_rejected_before_upload():
    p=workout_schema('multi_sport')['example_workout']
    p['workoutSegments'][1]['workoutSteps'][0]['stepOrder']=1
    with pytest.raises(ValueError,match='unique'):
        validate('create_workout',{'workout_json':p})


@pytest.mark.parametrize('sport',['walking','hiking'])
def test_legacy_sdk_sports_do_not_create_identityless_workouts(sport):
    assert workout_schema(sport)['creation_supported'] is False
    with pytest.raises(ValueError):build_workout(sport,'Invalid SDK sport',duration_seconds=300)
    p=workout_schema('running')['example_workout'];p['sportType']={'sportTypeId':17 if sport=='walking' else 18,'sportTypeKey':sport}
    with pytest.raises(ValueError):validate('create_workout',{'workout_json':p})


def test_new_mcp_helpers_are_readonly_and_build_without_account_write(tmp_path):
    import asyncio,json
    from garmin_connect_mcp.server import create_server
    from garmin_connect_mcp.service import GarminService
    from garmin_connect_mcp.auth import TokenStore
    calls=[]
    def runner(directory,method,args,kwargs):
        calls.append((method,args))
        if method=='get_activity_types':return CATALOG
        if method=='connectapi':return {'workoutSportTypes':[{'sportTypeKey':'pilates','sportTypeId':8}]}
        raise AssertionError('Unexpected mutation or endpoint')
    server=create_server(GarminService(TokenStore(tmp_path),runner))
    async def check():
        names={'list_garmin_workout_sports','build_garmin_workout','get_garmin_activity_schema','build_garmin_manual_activity'}
        tools=await server.list_tools();assert all(t.annotations.readOnlyHint for t in tools if t.name in names)
        for name,args in [('list_garmin_workout_sports',{}),('build_garmin_workout',{'sport':'pilates','workout_name':'Selected Pilates','duration_seconds':1200}),('get_garmin_activity_schema',{'type_key':'tennis_v2'}),('build_garmin_manual_activity',{'parameters':PARAMETERS})]:
            result=await server.call_tool(name,args);body=json.loads(result[0].text);assert 'error' not in body
        assert calls[0]==('connectapi',('/workout-service/workout/types',))
        assert all(method in {'connectapi','get_activity_types'} for method,args in calls)
    asyncio.run(check())


def test_update_multisport_order_error_identifies_actual_operation():
    p=workout_schema('multi_sport')['example_workout'];p['workoutId']=123
    p['workoutSegments'][1]['workoutSteps'][0]['stepOrder']=1
    with pytest.raises(ValueError) as exc:validate('update_workout',{'workout_id':123,'workout_json':p})
    assert exc.value.operation=='update_workout'


@pytest.mark.parametrize('sport,id_value',[('walking',17),('hiking',18),('invented',999)])
def test_multisport_cannot_hide_unsupported_segment_sport(sport,id_value):
    p=workout_schema('multi_sport')['example_workout']
    p['workoutSegments'][0]['sportType']={'sportTypeId':id_value,'sportTypeKey':sport}
    with pytest.raises(ValueError,match='supported Garmin workout sport'):
        validate('create_workout',{'workout_json':p})
