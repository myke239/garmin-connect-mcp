"""User-local official FIT SDK add-on for redistributable frozen applications."""
import base64
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path


def root():
    from .frozen_install import default_root
    return default_root()/'fit-support'


def decode(content):
    if importlib.util.find_spec('garmin_fit_sdk') is not None:
        from .fit_codec import decode as local_decode
        return local_decode(content)
    receipt=root()/'installation.json'
    if not receipt.is_file():
        from .runtime import RequestError
        raise RequestError('FIT_SUPPORT_REQUIRED')
    metadata=json.loads(receipt.read_text(encoding='utf-8'))
    python=Path(metadata['python']);script=Path(metadata['script'])
    private_root=root().absolute()
    if not python.absolute().is_relative_to(private_root) or not script.absolute().is_relative_to(private_root) or python.is_symlink() and os.name=='nt':
        raise ValueError('FIT support paths must stay within the private add-on')
    result=subprocess.run([str(python),str(script)],input=json.dumps({'content':base64.b64encode(content).decode()}),capture_output=True,text=True,timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if result.returncode or len(result.stdout)>32*1024*1024:raise ValueError('FIT codec failed or exceeded response bound')
    value=json.loads(result.stdout)
    if not value.get('ok'):raise ValueError('FIT content invalid or exceeds supported bounds')
    return value['result']


def setup():
    from .frozen_install import default_root
    directory=root();directory.mkdir(parents=True,exist_ok=True)
    if directory.is_symlink() or directory.is_junction():raise ValueError('FIT support root cannot be a link')
    environment=os.environ.copy()
    environment.update(UV_CACHE_DIR=str(directory/'cache'),UV_PYTHON_INSTALL_DIR=str(directory/'python'),UV_SYSTEM_CERTS='true',UV_PYTHON_PREFERENCE='only-managed')
    uv=default_root()/'tools'/('uv.exe' if os.name=='nt' else 'uv')
    if not uv.is_file():
        uv=directory/'tools'/('uv.exe' if os.name=='nt' else 'uv')
    if not uv.is_file():
        environment.update(UV_INSTALL_DIR=str(directory/'tools'),UV_NO_MODIFY_PATH='1')
        if os.name=='nt':
            bootstrap=['powershell','-NoProfile','-ExecutionPolicy','Bypass','-Command','irm https://astral.sh/uv/install.ps1 | iex']
        else:bootstrap=['sh','-c','curl --proto "=https" --tlsv1.2 -LsSf https://astral.sh/uv/install.sh | sh']
        subprocess.run(bootstrap,env=environment,check=True)
    release=directory/('runtime-'+uuid.uuid4().hex[:8])
    subprocess.run([str(uv),'venv','--python','3.13',str(release)],env=environment,check=True)
    python=release/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
    subprocess.run([str(uv),'pip','install','--python',str(python),'garmin-fit-sdk==21.218.0'],env=environment,check=True)
    # Copy only our MIT-licensed adapter, never Garmin's code.
    from importlib.resources import files
    script=release/'fit_codec.py';script.write_text(files('garmin_connect_mcp').joinpath('fit_codec.py').read_text(encoding='utf-8'),encoding='utf-8')
    subprocess.run([str(python),'-c','from garmin_fit_sdk import Decoder,Stream'],check=True)
    temporary=directory/'installation.json.new';temporary.write_text(json.dumps({'python':str(python),'script':str(script),'sdk_version':'21.218.0'}),encoding='utf-8');temporary.replace(directory/'installation.json')
    print('FIT support installed locally from PyPI. Garmin FIT Protocol License Agreement applies; no activation or cd required.')


if __name__=='__main__':setup()
