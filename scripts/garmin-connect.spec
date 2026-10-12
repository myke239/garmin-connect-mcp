from pathlib import Path
from PyInstaller.utils.hooks import collect_all,copy_metadata
root=Path(SPECPATH).parent
all_data=[];all_binaries=[];all_imports=[]
for package in ('garmin_connect_mcp','garminconnect','mcp','curl_cffi','ngrok','pystray','PIL','keyring','cryptography'):
    data,binaries,imports=collect_all(package,filter_submodules=lambda name:not name.startswith("mcp.cli"))
    all_data+=data;all_binaries+=binaries;all_imports+=imports
for name in ('garminconnect','mcp','ngrok','curl_cffi','keyring','cryptography','pystray','pillow','truststore','jsonschema','defusedxml','tzdata','requests','urllib3','certifi','pydantic','pydantic-core','starlette','uvicorn','sse-starlette','anyio','httpx','httpcore'):
    all_data+=copy_metadata(name)
all_data += [(str(root/'plugins'),'plugins'),(str(root/'.agents/plugins'),'marketplace-index'),(str(root/'LICENSE'),'.'),(str(root/'NOTICE'),'.')]
a=Analysis([str(root/'scripts/frozen_entry.py')],pathex=[str(root/'src')],binaries=all_binaries,datas=all_data,hiddenimports=all_imports,excludes=["garmin_fit_sdk"])
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='garmin-connect',console=True)
gui=EXE(pyz,a.scripts,[],exclude_binaries=True,name='garmin-connect-desktop',console=False)
coll=COLLECT(exe,gui,a.binaries,a.datas,name='garmin-connect')
