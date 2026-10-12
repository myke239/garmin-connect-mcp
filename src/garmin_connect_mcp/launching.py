"""Typed, fixed module launching for Python and frozen distributions."""
import runpy
import sys
from pathlib import Path
from collections.abc import Sequence

MODULES=frozenset({'manage','cli','server','worker','remote','tunnel','writes','archive','protected_storage','catalog_drift','desktop','background','diagnostics','frozen_install','fit_support','shortcut'})


def command(module: str, arguments: Sequence[str] = ()) -> list[str]:
    if module not in MODULES:
        raise ValueError('Unsupported internal module')
    if getattr(sys,'frozen',False):
        frozen_executable=Path(sys.executable)
        if frozen_executable.stem=='garmin-connect-desktop':frozen_executable=frozen_executable.with_name('garmin-connect.exe' if sys.platform=='win32' else 'garmin-connect')
        return [str(frozen_executable),'--internal-module',module,*arguments]
    executable=sys.executable[:-len('pythonw.exe')]+'python.exe' if sys.executable.lower().endswith('pythonw.exe') else sys.executable
    return [executable,'-m','garmin_connect_mcp.'+module,*arguments]


def main() -> None:
    arguments=sys.argv[1:]
    if len(arguments)>=2 and arguments[0]=='--internal-module':
        module=arguments[1]
        if module not in MODULES: raise SystemExit('Unsupported internal module')
        sys.argv=[sys.argv[0],*arguments[2:]]
        runpy.run_module('garmin_connect_mcp.'+module,run_name='__main__')
    elif not arguments:
        from .desktop import main as desktop_main
        desktop_main()
    else:
        from .manage import main as manage_main
        manage_main()


if __name__=='__main__': main()
