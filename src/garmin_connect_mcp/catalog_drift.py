"""Fixed-source public catalog drift audit; never execute downloaded Python."""
import ast
import hashlib
import json
import re
from importlib.metadata import version
from .yoga import CATALOG,POSES

SOURCES={'strength':'https://raw.githubusercontent.com/cyberjunky/python-garminconnect/master/garminconnect/exercises.py',
    'yoga':'https://connect.garmin.com/web-data/exercises/Yoga.json'}


def read_source(url):
    import truststore
    import requests
    truststore.inject_into_ssl()
    with requests.get(url,timeout=(10,20),stream=True,allow_redirects=False) as response:
        response.raise_for_status()
        content=bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content)>1000000: raise ValueError('Catalog source exceeds 1 MB')
    return bytes(content)


def compare(kind,content):
    from garminconnect.exercises import EXERCISES
    if kind=='strength':
        tree=ast.parse(content.decode('utf-8'))
        node=next((v.value for v in tree.body if isinstance(v,ast.AnnAssign) and isinstance(v.target,ast.Name) and v.target.id=='_RAW'),None)
        if node is None: raise ValueError('Upstream catalog shape changed')
        rows=ast.literal_eval(node)
        if not isinstance(rows,list) or len(rows)>10000 or any(not isinstance(v,tuple) or len(v)!=3 or not all(isinstance(k,str) and len(k)<=200 for k in v) for v in rows):
            raise ValueError('Invalid upstream catalog rows')
        upstream={(v[1],v[2]) for v in rows}
        pinned={(v['category'],v['exercise']) for v in EXERCISES}
    elif kind=='yoga':
        raw=json.loads(content)
        values=raw['categories']['POSE']['exercises']
        if not isinstance(values,dict) or len(values)>10000: raise ValueError('Upstream yoga shape changed')
        upstream={('POSE',key) for key in values}
        pinned={('POSE',key) for key in POSES}
    else: raise ValueError('Unknown catalog kind')
    if any(not re.fullmatch('[A-Z_0-9]*',part) for row in upstream for part in row):
        raise ValueError('Unexpected catalog identifier')
    added,removed=sorted(upstream-pinned),sorted(pinned-upstream)
    return {'kind':kind,'sdk_version':version('garminconnect'),'pinned_count':len(pinned),'upstream_count':len(upstream),
        'source':SOURCES[kind],'source_sha256':hashlib.sha256(content).hexdigest(),
        'added_count':len(added),'removed_count':len(removed),'added':added[:100],'removed':removed[:100],
        'truncated':len(added)>100 or len(removed)>100,'drift':bool(added or removed),
        'automatically_applied':False,'guidance':'Review upstream change via PR and SDK/live checks before accepting new identifiers.'}


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['check'])
    args=parser.parse_args()
    result=[compare(kind,read_source(url)) for kind,url in SOURCES.items()]
    print(json.dumps(result,indent=2))
    if any(v['drift'] for v in result): raise SystemExit(2)


if __name__=='__main__': main()
