"""Opt-in per-user tunnel watchdog and startup registration. Never kills arbitrary PIDs."""
import argparse
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from .auth import TokenStore,data_directory,restrict
from .launching import command

NAME='garmin-connect-mcp'


def stores():
    root=data_directory()/'background'
    return TokenStore(root/'state'),TokenStore(root/'stop')


def owned(value):
    pid=value.get('pid');nonce=value.get('nonce')
    if isinstance(pid,bool) or not isinstance(pid,int) or pid<1 or not isinstance(nonce,str) or len(nonce)!=32:
        return False
    try:
        if os.name=='nt':
            script='Get-CimInstance Win32_Process -Filter "ProcessId = '+str(pid)+'" | Select-Object -ExpandProperty CommandLine'
            result=subprocess.run(['powershell','-NoProfile','-Command',script],capture_output=True,text=True,timeout=5)
            line=result.stdout
        else:
            line=Path('/proc/'+str(pid)+'/cmdline').read_bytes().replace(b'\0',b' ').decode()
        return nonce in line and ('garmin_connect_mcp.background' in line or '--internal-module background' in line) and '--nonce' in line
    except (OSError,subprocess.SubprocessError): return False


def status() -> dict[str,Any]:
    store,_=stores()
    value=json.loads(store.load()) if store.exists() else {}
    return {'running':owned(value),'child_state':value.get('child_state','stopped'),
        'restart_count':value.get('restart_count',0),'oauth_guard_healthy':value.get('oauth_guard_healthy'), 'startup_installed':startup_path().exists()}


def start():
    if status()['running']: return status()
    from .manage import remote_available
    if not remote_available(): raise ValueError('Install remote extras first')
    if not TokenStore(data_directory()/'remote-tunnel').exists(): raise ValueError('Run tunnel-setup locally first')
    from .diagnostics import health
    if health()['reachable']:raise ValueError('Local tunnel port is occupied; manage the existing service before starting a new one')
    nonce=secrets.token_hex(16)
    _,stop_store=stores();stop_store.clear()
    options={'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
    if os.name=='nt': options['creationflags']=subprocess.CREATE_NO_WINDOW|subprocess.DETACHED_PROCESS
    else: options['start_new_session']=True
    child=subprocess.Popen(command('background',['run','--nonce',nonce]),**options)
    for _ in range(30):
        if child.poll() is not None: raise RuntimeError('Background process exited; run diagnostics')
        value=status()
        if value['running']: return value
        time.sleep(.1)
    raise RuntimeError('Background startup was not confirmed')


def stop():
    store,stop_store=stores()
    value=json.loads(store.load()) if store.exists() else {}
    if not owned(value): return {'running':False,'stopped':False}
    stop_store.save(json.dumps({'nonce':value['nonce']}))
    for _ in range(50):
        if not owned(value): return {'running':False,'stopped':True}
        time.sleep(.2)
    raise RuntimeError('Managed background process did not stop; inspect diagnostics')


def startup_path():
    if os.name=='nt':
        return Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs/Startup/GarminConnectMCP.vbs'
    return Path(os.environ.get('XDG_CONFIG_HOME') or str(Path.home()/'.config'))/'systemd/user/garmin-connect-mcp.service'


def install_startup():
    path=startup_path();path.parent.mkdir(parents=True,exist_ok=True)
    if path.is_symlink(): raise ValueError('Startup path cannot be a symlink')
    if path.exists() and 'Garmin Connect MCP managed startup' not in path.read_text(encoding='utf-8'):
        raise ValueError('Refusing to replace an unrelated startup entry')
    if os.name=='nt':
        line=subprocess.list2cmdline(command('background',['start'])).replace('"','""')
        text="' Garmin Connect MCP managed startup\nCreateObject(\"WScript.Shell\").Run \""+line+'\", 0, False\n'
    else:
        # systemd command syntax differs from shell syntax; quote each argument,
        # escaping percent specifiers and control characters rather than invoking a shell.
        def quote(value):
            if any(v in value for v in ('\n','\r','\0')): raise ValueError('Invalid service path')
            return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'
        line=' '.join(quote(v) for v in command('background',['run','--nonce',secrets.token_hex(16)]))
        directory=str(data_directory()).replace('\\','\\\\').replace('"','\\"').replace('%','%%')
        text='# Garmin Connect MCP managed startup\n[Unit]\nStartLimitIntervalSec=300\nStartLimitBurst=3\nDescription=Personal Garmin Connect MCP tunnel\nAfter=network-online.target\n[Service]\nType=simple\nExecStart='+line+'\nEnvironment="GARMIN_MCP_DATA_DIR='+directory+'"\nRestart=on-failure\nRestartSec=10\n[Install]\nWantedBy=default.target\n'
    if os.name!='nt':
        existing=subprocess.run(['systemctl','--user','show',path.name,'--property=FragmentPath','--value'],capture_output=True,text=True)
        fragment=getattr(existing,'stdout','').strip()
        if fragment and Path(fragment).absolute()!=path.absolute():raise ValueError('Refusing to replace another systemd unit with this name')
    path.write_text(text,encoding='utf-8')
    if os.name!='nt':
        path.chmod(0o600)
        subprocess.run(['systemctl','--user','daemon-reload'],check=True,capture_output=True)
        subprocess.run(['systemctl','--user','enable',str(path)],check=True,capture_output=True)
    return {'startup_installed':True,'path':str(path),'starts_now':False}


def uninstall_startup():
    path=startup_path()
    if path.exists():
        if path.is_symlink() or 'Garmin Connect MCP managed startup' not in path.read_text(encoding='utf-8'):
            raise ValueError('Refusing to remove an unrelated startup entry')
        if os.name!='nt':
            subprocess.run(['systemctl','--user','disable',str(path)],check=True,capture_output=True)
        path.unlink()
        if os.name!='nt':subprocess.run(['systemctl','--user','daemon-reload'],check=True,capture_output=True)
    return {'startup_installed':False}


def run(nonce):
    if not isinstance(nonce,str) or len(nonce)!=32 or any(v not in '0123456789abcdef' for v in nonce): raise ValueError('Invalid instance nonce')
    store,stop_store=stores()
    # Respect an existing owned instance; never compete for a fixed tunnel port.
    if status()['running']: raise RuntimeError('Managed background instance already running')
    state={'pid':os.getpid(),'nonce':nonce,'restart_count':0,'child_state':'starting'}
    store.save(json.dumps(state))
    child=None
    stopping=False
    def request_stop(*args):
        nonlocal stopping
        stopping=True
    signal.signal(signal.SIGTERM,request_stop)
    signal.signal(signal.SIGINT,request_stop)
    try:
        for attempt in range(4):
            state.update(restart_count=attempt,child_state='starting');store.save(json.dumps(state))
            child=subprocess.Popen(command('tunnel',['run']),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            state['child_state']='running';store.save(json.dumps(state))
            started=time.monotonic();next_health=started+30;failures=0
            while child.poll() is None:
                if stop_store.exists() and json.loads(stop_store.load()).get('nonce')==nonce: stopping=True
                if stopping: return
                if time.monotonic()>=next_health:
                    from .diagnostics import health
                    state['oauth_guard_healthy']=health()['oauth_guard_verified']
                    store.save(json.dumps(state));next_health=time.monotonic()+10
                    failures=0 if state['oauth_guard_healthy'] else failures+1
                    if failures>=3:
                        child.terminate()
                        try:child.wait(timeout=5)
                        except subprocess.TimeoutExpired:child.kill();child.wait()
                        break
                time.sleep(.2)
            if stopping: return
            state['child_state']='restarting';store.save(json.dumps(state))
            for _ in range(50):
                if stop_store.exists() and json.loads(stop_store.load()).get('nonce')==nonce:return
                if stopping:return
                time.sleep(.2)
        state['child_state']='failed';store.save(json.dumps(state))
        raise SystemExit(1)
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=5)
            except subprocess.TimeoutExpired:child.kill();child.wait()
        if state["child_state"]!="failed":state["child_state"]="stopped"
        store.save(json.dumps(state))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['start','stop','status','install','uninstall','run'])
    parser.add_argument('--nonce')
    args=parser.parse_args()
    if args.command=='run':run(args.nonce);return
    actions={'start':start,'stop':stop,'status':status,'install':install_startup,'uninstall':uninstall_startup}
    print(json.dumps(actions[args.command]()))


if __name__=='__main__':main()
