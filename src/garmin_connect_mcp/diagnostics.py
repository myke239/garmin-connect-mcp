"""Local diagnostic output never includes tokens, workout content or locations."""
import json
from pathlib import Path
from typing import Any
from urllib.request import urlopen
from urllib.error import HTTPError, URLError
from . import __version__
from .auth import TokenStore,data_directory


def health(port: int = 8787) -> dict[str, Any]:
    if isinstance(port,bool) or not 1024<=port<=65535: raise ValueError('Unprivileged port required')
    try:
        with urlopen('http://127.0.0.1:'+str(port)+'/mcp/garmin-connect/',timeout=2) as response:
            return {'reachable':True,'status':response.status,'oauth_guard_verified':False}
    except HTTPError as error:
        return {'reachable':True,'status':error.code,'oauth_guard_verified':error.code==401}
    except (URLError,TimeoutError,OSError):
        return {'reachable':False,'status':None,'oauth_guard_verified':False}


def report() -> dict[str, Any]:
    from .writes import WriteService
    from .protected_storage import configuration
    from .manage import remote_available
    from .background import status
    store=TokenStore()
    writes=WriteService()
    value={'version':__version__,'session_saved':store.exists(),'garmin_verified':False,
        'writes_enabled':writes.enabled(),'remote_dependencies':remote_available(),
        'private_storage':'windows-dpapi' if __import__('os').name=='nt' else 'linux-secret-service' if configuration(data_directory()) else 'owner-only',
        'background':status(),'local_http':health()}
    if writes.settings.exists():
        settings=json.loads(writes.settings.load())
        value['allowed_operations']=settings.get('operations','all enabled operations')
    return value


def main() -> None:
    print(json.dumps(report(),indent=2))


if __name__=='__main__': main()
