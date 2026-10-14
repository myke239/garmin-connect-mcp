"""Install the frozen distribution without Python, activation or a checkout."""
import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from . import __version__


def default_root():
    if os.name=='nt':return Path(os.environ['LOCALAPPDATA'])/'Programs/GarminConnectMCP'
    base=Path(os.environ.get('XDG_DATA_HOME') or str(Path.home()/'.local/share'))
    if not base.is_absolute():raise ValueError('XDG_DATA_HOME must be absolute')
    return base/'garmin-connect-mcp/application'


def install():
    if not getattr(sys,'frozen',False):raise ValueError('Use the source installer when running Python')
    root=default_root()
    if root.is_symlink() or root.is_junction():raise ValueError('Installation root cannot be a link')
    release=root/'releases'/(__version__+'-frozen-'+uuid.uuid4().hex[:8]);release.mkdir(parents=True)
    source=Path(sys.executable).parent
    executable=release/Path(sys.executable).name
    shutil.copy2(sys.executable,executable)
    gui=source/("garmin-connect-desktop.exe" if os.name=="nt" else "garmin-connect-desktop")
    if gui.is_file():shutil.copy2(gui,release/gui.name)
    shutil.copytree(source/'_internal',release/'_internal')
    if os.name!='nt':root.chmod(0o700);executable.chmod(0o700)
    marketplace=release/'marketplace'
    resources=Path(getattr(sys,'_MEIPASS'))
    shutil.copytree(resources/'plugins',marketplace/'plugins')
    shutil.copytree(resources/'marketplace-index',marketplace/'.agents/plugins')
    path=marketplace/'plugins/garmin-connect/.mcp.json';value=json.loads(path.read_text(encoding='utf-8'))
    value['mcpServers']['garmin-connect'].update(command=str(executable),args=['serve'])
    path.write_text(json.dumps(value,indent=2),encoding='utf-8')
    # Verify the newly installed binary before publishing pointers.
    import subprocess
    subprocess.run([str(executable),'doctor'],check=True,stdout=subprocess.DEVNULL)
    metadata={'version':__version__,'python':str(executable),'kind':'frozen','marketplace':str(marketplace),'remote':True,'launcher':str(executable)}
    text=json.dumps(metadata,indent=2)
    (release/'installation.json').write_text(text,encoding='utf-8')
    temporary=root/'installation.json.new';temporary.write_text(text,encoding='utf-8');temporary.replace(root/'installation.json')
    from .shortcut import install as install_shortcut
    install_shortcut(executable,frozen=True)
    print('Installed Garmin Connect '+__version__+'. Run this absolute path with desktop, login, install-plugin or serve: '+str(executable))




def register_bundle(remove=False):
    """Register only an installer-owned versioned bundle; never delete private data."""
    if not getattr(sys,'frozen',False):raise ValueError('Installer registration requires the frozen executable')
    root=default_root().resolve()
    source=Path(sys.executable).resolve().parent
    if source.parent != root/'releases' or source.name != __version__+'-installer':
        raise ValueError('Installer bundle must use the standard versioned installation path')
    receipt=root/'installation.json'
    if remove:
        if receipt.is_file():
            current=json.loads(receipt.read_text(encoding='utf-8'))
            if current.get('launcher')==str(source/'garmin-connect.exe'):receipt.unlink()
        return
    resources=Path(getattr(sys,'_MEIPASS'))
    marketplace=source/'marketplace'
    if marketplace.is_symlink() or marketplace.is_junction():raise ValueError('Marketplace cannot be a link')
    if marketplace.exists():
        # Preserve the installed manifest on a repair; only republish its receipt.
        manifest=marketplace/'plugins/garmin-connect/.mcp.json'
    else:
        shutil.copytree(resources/'plugins',marketplace/'plugins')
        shutil.copytree(resources/'marketplace-index',marketplace/'.agents/plugins')
    manifest=marketplace/'plugins/garmin-connect/.mcp.json'
    value=json.loads(manifest.read_text(encoding='utf-8'))
    executable=source/'garmin-connect.exe'
    value['mcpServers']['garmin-connect'].update(command=str(executable),args=['serve'])
    manifest.write_text(json.dumps(value,indent=2),encoding='utf-8')
    import subprocess
    subprocess.run([str(executable),'doctor'],check=True,stdout=subprocess.DEVNULL)
    metadata={'version':__version__,'python':str(executable),'kind':'frozen','marketplace':str(marketplace),'remote':True,'launcher':str(executable)}
    text=json.dumps(metadata,indent=2)
    (source/'installation.json').write_text(text,encoding='utf-8')
    temporary=root/'installation.json.new';temporary.write_text(text,encoding='utf-8');temporary.replace(receipt)

if __name__=='__main__':
    if sys.argv[1:]==['--register-bundle']:register_bundle()
    elif sys.argv[1:]==['--unregister-bundle']:register_bundle(remove=True)
    elif not sys.argv[1:]:install()
    else:raise SystemExit('Unsupported installer action')
