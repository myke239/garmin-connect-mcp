import asyncio,json
import pytest
from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.writes import WriteService,execute
from garmin_connect_mcp import protected_storage
from garmin_connect_mcp.catalog_drift import compare
from test_writes import CASES,FakeClient


def test_operation_allowlist_rechecked_at_prepare_commit_and_worker(tmp_path):
    service=WriteService(tmp_path,runner=lambda *args:pytest.fail('Denied operation must not reach worker'))
    service.settings.save(json.dumps({'enabled':True,'operations':['create_workout']}))
    with pytest.raises(RequestError,match='WRITE_OPERATION_DENIED'):
        service.prepare('add_weight',CASES['add_weight'],'forbidden-operation')
    draft=service.prepare('create_workout',CASES['create_workout'],'allowed-then-revoked')
    service.settings.save(json.dumps({'enabled':True,'operations':[]}))
    with pytest.raises(RequestError,match='WRITE_OPERATION_DENIED'): service.commit(draft['draft_id'])
    client=FakeClient()
    with pytest.raises(RequestError,match='WRITE_OPERATION_DENIED'): execute(client,tmp_path,draft['draft_id'])
    assert not client.calls and service.status(draft['draft_id'])['status']=='prepared'
    service.settings.save(json.dumps({'enabled':True,'operations':'all'}))
    with pytest.raises(RequestError,match='WRITE_OPERATION_DENIED'): service.require_enabled('create_workout')


@pytest.mark.parametrize('profile',['read-only','recovery','planning','performance'])
def test_tool_profiles_remove_callable_handlers(tmp_path,profile):
    server=create_server(GarminService(TokenStore(tmp_path)),tool_profile=profile)
    tools=asyncio.run(server.list_tools());names={t.name for t in tools}
    assert 'connection_status' in names
    if profile=='read-only': assert all(t.annotations.readOnlyHint for t in tools)
    if profile in {'read-only','recovery','performance'}:
        assert 'commit_garmin_write' not in names
        with pytest.raises(Exception): asyncio.run(server.call_tool('commit_garmin_write',{'draft_id':'x'*24}))
    if profile=='planning': assert 'commit_garmin_workout_creation' in names and 'get_garmin_recovery' not in names
    if profile=='performance': assert 'get_archived_activity_analysis' in names
    with pytest.raises(ValueError,match='Unknown tool profile'):
        create_server(GarminService(TokenStore(tmp_path)),tool_profile='unsafe')


class ProtectedBackend:
    def __init__(self):self.values={}
    def get_password(self,s,u):return self.values.get((s,u))
    def set_password(self,s,u,v):self.values[s,u]=v


def test_protected_crypto_missing_key_fails_closed(tmp_path,monkeypatch):
    pytest.importorskip('cryptography')
    selected=ProtectedBackend();monkeypatch.setattr(protected_storage,'backend',lambda:selected)
    protected_storage.cipher(tmp_path,create=True)
    (tmp_path/protected_storage.MARKER).write_text(json.dumps({'backend':'secret-service','version':1}))
    child=tmp_path/'child';child.mkdir()
    raw=b'{"synthetic":"secret"}'
    encrypted=protected_storage.encode(child,raw)
    assert encrypted.startswith(b'GCMCP1:') and b'secret' not in encrypted
    assert protected_storage.decode(child,encrypted)==raw
    selected.values.clear()
    with pytest.raises(RuntimeError,match='unavailable'):protected_storage.decode(child,encrypted)
    with pytest.raises(RuntimeError,match='unavailable'):protected_storage.decode(child,raw)


def test_plaintext_keyring_backend_refused(monkeypatch):
    keyring=pytest.importorskip('keyring')
    monkeypatch.setattr(keyring,'get_keyring',lambda:ProtectedBackend())
    with pytest.raises(RuntimeError,match='fallback refused'):protected_storage.backend()


@pytest.mark.skipif(__import__('os').name=='nt',reason='Linux optional storage migration')
def test_migration_reentrant_and_retains_settings_journal(tmp_path,monkeypatch):
    pytest.importorskip('cryptography')
    selected=ProtectedBackend();monkeypatch.setattr(protected_storage,'backend',lambda:selected)
    account=TokenStore(tmp_path);account.save('{"synthetic":"session"}')
    journal=TokenStore(tmp_path/'write-journal');journal.save('{"draft":"prepared"}')
    result=protected_storage.migrate(tmp_path)
    assert result['encrypted_stores']==2
    assert account.load()=='{"synthetic":"session"}' and journal.load()=='{"draft":"prepared"}'
    assert account.path.read_bytes().startswith(b'GCMCP1:')
    assert protected_storage.migrate(tmp_path)['encrypted_stores']==2


def test_drift_parser_never_executes_code_and_reports_changes(tmp_path):
    source=b'_RAW: list = [("Test", "SQUAT", "NEW_TEST")]\nraise RuntimeError("must never execute")'
    result=compare('strength',source)
    assert result['drift'] and result['added']==[('SQUAT','NEW_TEST')] and not result['automatically_applied']
    result=compare('yoga',json.dumps({'categories':{'POSE':{'exercises':{'CAT':{},'TEST_NEW_POSE':{}}}}}).encode())
    assert result['added']==[('POSE','TEST_NEW_POSE')]
    with pytest.raises(ValueError): compare('strength',b'_RAW: list = __import__("os").system("bad")')


def test_default_writes_and_persisted_revocation_at_every_boundary(tmp_path):
    service=WriteService(tmp_path,runner=lambda *args:pytest.fail('Revoked write must not reach worker'))
    assert service.enabled() and not service.settings.exists()
    draft=service.prepare('add_weight',CASES['add_weight'],'default-enabled-draft')
    service.settings.save(json.dumps({'enabled':False,'operations':['add_weight']}))
    reopened=WriteService(tmp_path,runner=service.runner)
    assert not reopened.enabled()
    with pytest.raises(RequestError,match='WRITES_DISABLED'):
        reopened.prepare('add_weight',CASES['add_weight'],'disabled-new-draft')
    with pytest.raises(RequestError,match='WRITES_DISABLED'): reopened.commit(draft['draft_id'])
    client=FakeClient()
    with pytest.raises(RequestError,match='WRITES_DISABLED'): execute(client,tmp_path,draft['draft_id'])
    assert not client.calls and reopened.status(draft['draft_id'])['status']=='prepared'


@pytest.mark.parametrize('settings',[{}, {'enabled':'true'}, {'enabled':1}, {'enabled':None}])
def test_existing_ambiguous_enable_setting_is_not_promoted(tmp_path,settings):
    service=WriteService(tmp_path)
    service.settings.save(json.dumps(settings))
    assert not service.enabled()
    with pytest.raises(RequestError,match='WRITES_DISABLED'):service.require_enabled('create_workout')
