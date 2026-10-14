"""Prepare a public-file review report, without uploading or collecting private state."""
import argparse
import hashlib
import json
from pathlib import Path

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('file',type=Path)
    parser.add_argument('--product',required=True);parser.add_argument('--detection',required=True)
    parser.add_argument('--release-url',required=True)
    args=parser.parse_args()
    if not args.release_url.startswith('https://github.com/myke239/garmin-connect-mcp/releases/'):
        parser.error('Use a published project release URL; never submit private data')
    if args.file.suffix.lower() not in {'.exe','.zip'}:parser.error('Review public release executable/archive only')
    print(json.dumps({'vendor':'Das Kreb','project':'Garmin Connect MCP','filename':args.file.name,
        'sha256':hashlib.sha256(args.file.read_bytes()).hexdigest(),'bytes':args.file.stat().st_size,
        'security_product':args.product,'detection':args.detection,'release_url':args.release_url,
        'report_status':'Prepared, not submitted; vendor review/clearance is not established.'},indent=2))
