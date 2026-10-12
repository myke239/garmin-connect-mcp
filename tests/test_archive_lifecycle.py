import json
import pytest
from garmin_connect_mcp.analytics import analyse, samples
from garmin_connect_mcp.archive import Archive, extract, parse
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.lifecycle import fingerprint, clone
from garmin_connect_mcp.writes import WriteService, execute, validate
from test_writes import WORKOUT
from test_sdk_write_contracts import Transport
from garminconnect import Garmin
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from audit_fixtures import fit_activity


def test_archive_opt_in_checksum_privacy_and_analysis(tmp_path):
    archive=Archive(tmp_path)
    with pytest.raises(RequestError,match='ARCHIVE_DISABLED'):
        archive.save('123',fit_activity())
    archive.settings.save(json.dumps({'enabled':True}))
    raw=fit_activity()
    saved=archive.save('123',raw)
    assert saved['sample_count']==2
    content=json.loads(archive.record('123').load())
    assert 'raw_fit_base64' not in content and 'serial_number' not in json.dumps(content)
    assert archive.analysis('123')['power_curve'][0]['best_average_power_w'] is None
    archive.save('123',raw,True)
    assert json.loads(archive.record('123').load())['raw_fit_base64']
    with pytest.raises(ValueError,match='checksum'):
        extract(raw[:-2]+b'xx')


def test_archive_zip_bomb_and_multiple_fit_refused():
    import io,zipfile
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('../a.fit',fit_activity());z.writestr('b.fit',fit_activity())
    with pytest.raises(ValueError,match='Exactly one'):
        extract(output.getvalue())


def test_full_resolution_power_drift_and_missing_zero():
    rows=[{'timestamp_s':i,'power_w':100 if i<600 else 200,'heart_rate_bpm':100 if i<600 else 110,'speed_m_s':3} for i in range(1200)]
    result=analyse(rows)
    assert result['power_curve'][3]['best_average_power_w']==200
    assert result['heart_rate_speed_drift_percent']==pytest.approx(10)
    rows[400]['timestamp_s']+=.5
    result=analyse(rows)
    assert result['heart_rate_speed_drift_percent'] is None
    assert all(x['best_average_power_w'] is None for x in result['power_curve'])
    assert analyse([{'timestamp_s':i,'power_w':0} for i in range(60)])['power_curve'][0]['best_average_power_w']==0
    assert analyse([{'timestamp_s':i,'power_w':None} for i in range(60)])['power_curve'][0]['best_average_power_w'] is None


def test_richer_samples_drop_location_and_missing():
    raw={'metricDescriptors':[{'key':'directTimestamp','metricsIndex':0},{'key':'directPower','metricsIndex':1},{'key':'directLatitude','metricsIndex':2}],
        'activityDetailMetrics':[{'metrics':[1000,200,50]},{'metrics':[2000,None,51]}]}
    result=samples(raw,'power',2)
    assert result['samples']==[{'timestamp_unix_ms':1000,'power_w':200},{'timestamp_unix_ms':2000,'power_w':None}]
    assert samples(raw,'speed',2)['available'] is False


@pytest.mark.parametrize('operation',['rename_workout','delete_workout','schedule_existing_workouts'])
def test_real_sdk_custom_workout_operations_once(tmp_path,operation):
    client=Garmin();client.client=Transport()
    original=client.get_workout_by_id(123)
    target={'workout_id':'123','expected_name':'Synthetic','expected_content_sha256':fingerprint(original)}
    parameters={'rename_workout':{**target,'workout_name':'New name'},'delete_workout':{**target,'confirm_calendar_removal':True},
        'schedule_existing_workouts':{'workouts':[{'workout_id':'123','date_str':'2026-10-12'},{'workout_id':'123','date_str':'2026-10-13'}]}}[operation]
    service=WriteService(tmp_path);service.settings.save(json.dumps({'enabled':True}))
    draft=service.prepare(operation,parameters,'custom-operation-test')
    result=execute(client,tmp_path,draft['draft_id'])
    assert result['status']=='completed',result
    assert len(client.client.calls)==(2 if operation=='schedule_existing_workouts' else 1)
    assert execute(client,tmp_path,draft['draft_id'])==result
    if operation=='rename_workout':
        body=client.client.calls[0][2]['json']
        assert body['workoutName']=='New name' and body['workoutSegments']==[]


def test_changed_template_and_duplicate_batch_rejected(tmp_path):
    service=WriteService(tmp_path);service.settings.save(json.dumps({'enabled':True}))
    draft=service.prepare('delete_workout',{'workout_id':'123','expected_name':'Synthetic','expected_content_sha256':'0'*64,'confirm_calendar_removal':True},'changed-target-test')
    client=Garmin();client.client=Transport()
    result=execute(client,tmp_path,draft['draft_id'])
    assert result['status']=='rejected' and result['error']['code']=='WORKOUT_TARGET_CHANGED'
    assert not client.client.calls
    with pytest.raises(ValueError,match='Duplicate'):
        validate('schedule_existing_workouts',{'workouts':[{'workout_id':'123','date_str':'2026-10-12'}]*2})


def test_batch_partial_failure_keeps_completed_rows_without_replay(tmp_path):
    client=Garmin();client.client=Transport()
    original=client.schedule_workout
    def schedule(workout_id,date_str):
        if date_str.endswith('13'): raise RequestError('NETWORK_ERROR')
        return original(workout_id,date_str)
    client.schedule_workout=schedule
    service=WriteService(tmp_path);service.settings.save(json.dumps({'enabled':True}))
    draft=service.prepare('schedule_existing_workouts',{'workouts':[{'workout_id':'123','date_str':f'2026-10-{day}'} for day in (12,13)]},'partial-batch-test')
    result=execute(client,tmp_path,draft['draft_id'])
    assert result['status']=='unknown' and len(result['steps'])==1
    assert execute(client,tmp_path,draft['draft_id'])==result
    assert len(client.client.calls)==1


def test_clone_strips_server_fields_and_preserves_steps():
    raw={**WORKOUT,'workoutId':123,'ownerId':456}
    class Backend:
        def fresh_call(self,*args): return raw
    result=clone(Backend(),'123','Clone')
    assert 'workoutId' not in result['workout_json']
    assert result['workout_json']['workoutSegments']==WORKOUT['workoutSegments']
