"""Optional application menu shortcut; does not enable background startup."""
import os
import subprocess
import sys
from pathlib import Path


def install(runtime, frozen=False):
    runtime=Path(runtime)
    if os.name=='nt':
        import win32com.client
        directory=Path(os.environ['APPDATA'])/'Microsoft/Windows/Start Menu/Programs'
        directory.mkdir(parents=True,exist_ok=True)
        path=directory/'Garmin Connect MCP.lnk'
        if path.is_symlink():raise ValueError('Shortcut cannot be a symlink')
        shortcut=win32com.client.Dispatch('WScript.Shell').CreateShortcut(str(path))
        if path.exists() and shortcut.Description!='Garmin Connect local setup':raise ValueError('Refusing to replace an unrelated shortcut')
        gui=runtime.with_name('garmin-connect-desktop.exe') if frozen else runtime.with_name('pythonw.exe')
        shortcut.TargetPath=str(gui if gui.exists() else runtime)
        shortcut.Arguments=subprocess.list2cmdline(['--internal-module','desktop','--tray'] if frozen else ['-m','garmin_connect_mcp.desktop','--tray'])
        shortcut.WorkingDirectory=str(runtime.parent);shortcut.Description='Garmin Connect local setup';shortcut.Save()
    else:
        base=Path(os.environ.get('XDG_DATA_HOME') or str(Path.home()/'.local/share'))
        if not base.is_absolute():raise ValueError('XDG_DATA_HOME must be absolute')
        directory=base/'applications';directory.mkdir(parents=True,exist_ok=True)
        args=[str(runtime),'desktop','--tray'] if frozen else [str(runtime),'-m','garmin_connect_mcp.desktop','--tray']
        def quote(value):
            if any(v in value for v in ('\n','\r','\0')):raise ValueError('Invalid shortcut path')
            return '"'+value.replace('\\','\\\\').replace('"','\\"').replace('%','%%')+'"'
        path=directory/'garmin-connect-mcp.desktop'
        if path.is_symlink():raise ValueError('Shortcut cannot be a symlink')
        path.write_text('[Desktop Entry]\nType=Application\nName=Garmin Connect\nComment=Local Garmin account and phone setup\nExec='+' '.join(quote(v) for v in args)+'\nTerminal=false\nCategories=Utility;\n',encoding='utf-8')
        path.chmod(0o600)


if __name__=='__main__':install(sys.argv[1],len(sys.argv)>2 and sys.argv[2]=='frozen')
