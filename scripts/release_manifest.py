"""Create public release integrity records from a build bundle, never account data."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess


def manifest(bundle):
    bundle=bundle.resolve()
    from PyInstaller.archive.readers import CArchiveReader
    for executable in bundle.glob('garmin-connect*.exe'):
        archive=CArchiveReader(str(executable))
        for name in archive.toc:
            if name.endswith('.pyz') and any('garmin_fit_sdk' in module for module in archive.open_embedded_archive(name).toc):
                raise ValueError('Restricted FIT SDK is forbidden inside executable archives')
    files=[]
    for path in sorted(bundle.rglob('*')):
        if path.is_symlink():raise ValueError('Release bundle cannot contain links')
        if not path.is_file():continue
        relative=path.relative_to(bundle).as_posix()
        if 'garmin_fit_sdk' in relative:raise ValueError('Restricted FIT SDK is forbidden in public executables')
        files.append({'path':relative,'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
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
