"""Create public release integrity records from a build bundle, never account data."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess


def manifest(bundle, *, allow_internal_links=False):
    bundle=bundle.resolve()
    files=[]
    for path in sorted(bundle.rglob('*')):
        relative=path.relative_to(bundle).as_posix()
        if 'garmin_fit_sdk' in relative:raise ValueError('Restricted FIT SDK is forbidden in public executables')
        if path.is_symlink():
            target=os.readlink(path)
            if (not allow_internal_links or Path(target).is_absolute()
                    or 'garmin_fit_sdk' in target):
                raise ValueError('Release bundle link is not permitted')
            try:
                resolved=path.resolve(strict=True)
            except (OSError,RuntimeError) as error:
                raise ValueError('Release bundle link is broken or cyclic') from error
            if not resolved.is_relative_to(bundle):
                raise ValueError('Release bundle link escapes bundle')
            files.append({'path':relative,'type':'symlink','target':target})
            continue
        if not path.is_file():continue
        files.append({'path':relative,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    for executable in bundle.iterdir():
        if not executable.is_file() or not (executable.name in {'garmin-connect', 'garmin-connect-desktop'} or executable.name.endswith('.exe')):
            continue
        from PyInstaller.archive.readers import CArchiveReader
        archive=CArchiveReader(str(executable))
        for name in archive.toc:
            if name.endswith('.pyz') and any('garmin_fit_sdk' in module for module in archive.open_embedded_archive(name).toc):
                raise ValueError('Restricted FIT SDK is forbidden inside executable archives')
    if not files:raise ValueError('Empty bundle')
    return {'vendor':'Das Kreb','product':'Garmin Connect MCP','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        'source_dirty':bool(subprocess.check_output(['git','status','--porcelain'],text=True).strip()),
        'files':files,'build_environment_packages':sorted([{'name':d.metadata['Name'],'version':d.version} for d in importlib.metadata.distributions()],key=lambda v:v['name'].lower()),
        'inventory_scope':'Build-environment package inventory plus final bundle file hashes; not a claim that every build dependency is shipped.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('bundle',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args()
    if args.output.resolve().is_relative_to(args.bundle.resolve()):parser.error('Manifest output must be outside bundle')
    args.output.write_text(json.dumps(manifest(args.bundle),indent=2)+'\n',encoding='utf-8')
