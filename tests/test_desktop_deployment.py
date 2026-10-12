import json,os,subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from garmin_connect_mcp import background,launching
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.diagnostics import health,report


def test_fixed_frozen_launch_commands(monkeypatch):
    assert launching.command('worker')[1:]==['-m','garmin_connect_mcp.worker']
    monkeypatch.setattr(launching.sys,'frozen',True,raising=False)
    assert launching.command('worker',['arg'])[1:]==['--internal-module','worker','arg']
    with pytest.raises(ValueError): launching.command('os')


def test_startup_only_overwrites_owned_entry_and_no_shell_injection(tmp_path,monkeypatch):
    path=tmp_path/'startup-service'
    monkeypatch.setattr(background,'startup_path',lambda:path)
    calls=[]
    monkeypatch.setattr(background.subprocess,'run',lambda args,**kwargs:calls.append(args) or SimpleNamespace(returncode=0))
    path.write_text('Unrelated startup')
    with pytest.raises(ValueError,match='unrelated'):background.install_startup()
    with pytest.raises(ValueError,match='unrelated'):background.uninstall_startup()
    path.unlink()
    value=background.install_startup()
    assert value['starts_now'] is False and 'Garmin Connect MCP managed startup' in path.read_text()
    background.uninstall_startup()
    assert not path.exists()
    assert all(not args[0].endswith('bash') for args in calls)


def test_stale_pid_stop_never_terminates_other_process(tmp_path,monkeypatch):
    state=TokenStore(tmp_path/'state');stop=TokenStore(tmp_path/'stop')
    state.save(json.dumps({'pid':os.getpid(),'nonce':'0'*32}))
    monkeypatch.setattr(background,'stores',lambda:(state,stop))
    assert background.stop()=={'running':False,'stopped':False}
    assert not stop.exists()


def test_watchdog_bounded_restarts_and_state(tmp_path,monkeypatch):
    state=TokenStore(tmp_path/'state');stop=TokenStore(tmp_path/'stop')
    monkeypatch.setattr(background,'stores',lambda:(state,stop))
    monkeypatch.setattr(background,'status',lambda:{'running':False})
    monkeypatch.setattr(background.time,'sleep',lambda delay:None)
    monkeypatch.setattr(background.signal,'signal',lambda *args:None)
    children=[]
    class Child:
        def __init__(self,*args,**kwargs):children.append(self)
        def poll(self):return 1
    monkeypatch.setattr(background.subprocess,'Popen',Child)
    with pytest.raises(SystemExit):background.run('a'*32)
    assert len(children)==4
    value=json.loads(state.load());assert value['restart_count']==3


def test_redacted_diagnostics_missing_session(tmp_path,monkeypatch):
    monkeypatch.setenv('GARMIN_MCP_DATA_DIR',str(tmp_path))
    monkeypatch.setattr('garmin_connect_mcp.diagnostics.health',lambda:{'reachable':False})
    value=report()
    assert not value['session_saved'] and value['garmin_verified'] is False
    assert 'authtoken' not in json.dumps(value)
    with pytest.raises(ValueError):health(True)


def test_fit_addon_missing_and_path_escape_fail_closed(tmp_path,monkeypatch):
    from garmin_connect_mcp import fit_support
    from garmin_connect_mcp.runtime import RequestError
    original=fit_support.importlib.util.find_spec
    monkeypatch.setattr(fit_support.importlib.util,'find_spec',lambda name:None if name=='garmin_fit_sdk' else original(name))
    monkeypatch.setattr(fit_support,'root',lambda:tmp_path)
    with pytest.raises(RequestError,match='FIT_SUPPORT_REQUIRED'):fit_support.decode(b'bad')
    (tmp_path/'installation.json').write_text(json.dumps({'python':str(tmp_path.parent/'outside'),'script':str(tmp_path/'script.py')}))
    with pytest.raises(ValueError,match='private add-on'):fit_support.decode(b'bad')


def test_cadence_source_unit_preserved():
    from garmin_connect_mcp.analytics import samples
    raw={'metricDescriptors':[{'key':'directDoubleCadence','metricsIndex':0,'unit':{'key':'stepsPerMinute','factor':1}}],
        'activityDetailMetrics':[{'metrics':[170]}]}
    value=samples(raw,'cadence',1)
    assert value['samples'][0]['cadence_raw']==170 and value['source_unit']['key']=='stepsPerMinute'
    assert not value['unit_factor_applied']
