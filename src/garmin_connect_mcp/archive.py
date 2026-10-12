"""Opt-in local archive, sanitized FIT records and private atomic storage."""
import base64
import hashlib
import io
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from .auth import TokenStore
from .data import number, validate_id
from .runtime import RequestError, session_lock

LIMIT = 16*1024*1024


def extract(content):
    if not isinstance(content, bytes) or not 1 <= len(content) <= LIMIT:
        raise ValueError('Original recording must be at most 16 MiB')
    if content[:2] == b'PK':
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 20 or sum(item.file_size for item in entries) > LIMIT:
                raise ValueError('Oversized recording archive')
            fits = [item for item in entries if item.filename.lower().endswith('.fit') and not item.is_dir()]
            if len(fits) != 1 or fits[0].flag_bits & 1:
                raise ValueError('Exactly one unencrypted FIT recording is required')
            content = archive.read(fits[0])  # Never extract user-controlled paths.
    from garminconnect.fit import _calcCRC
    if len(content) < 14 or content[0] not in (12,14) or content[8:12] != b'.FIT' or len(content) != content[0]+int.from_bytes(content[4:8],'little')+2:
        raise ValueError('Invalid FIT recording header/length')
    crc = 0
    for value in content:
        crc = _calcCRC(crc,value)
    if crc:
        raise ValueError('Invalid FIT checksum')
    return content


def parse(content):
    from garmin_fit_sdk import Decoder, Stream
    count = 0
    def listener(kind, value):
        nonlocal count
        count += 1
        if count > 100000:
            raise ValueError('Recording message limit exceeded')
    messages, errors = Decoder(Stream.from_byte_array(bytearray(content))).read(mesg_listener=listener)
    if errors or not messages.get('file_id_mesgs') or messages['file_id_mesgs'][0].get('type') != 'activity' or not messages.get('session_mesgs'):
        raise ValueError('Unsupported activity recording')
    raw = messages.get('record_mesgs', [])
    if len(raw) > 50000:
        raise ValueError('Recording sample limit exceeded')
    rows = []
    for row in raw:
        stamp = row.get('timestamp')
        if not isinstance(stamp, datetime) or stamp.tzinfo is None:
            raise ValueError('Recording timestamp must have a timezone')
        rows.append({'timestamp_s': stamp.timestamp(), 'heart_rate_bpm': number(row.get('heart_rate')),
            'power_w': number(row.get('power')), 'cadence_rpm': number(row.get('cadence')),
            'speed_m_s': number(row.get('enhanced_speed',row.get('speed'))),
            'elevation_m': number(row.get('enhanced_altitude',row.get('altitude'))),
            'distance_m': number(row.get('distance'))})
    # Coordinates, developer fields, serial numbers and text are never copied.
    return rows


class Archive:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.settings = TokenStore(self.directory/'archive-settings')
    def require_enabled(self):
        if not self.settings.exists() or json.loads(self.settings.load()).get('enabled') is not True:
            raise RequestError('ARCHIVE_DISABLED')
    def record(self, activity_id):
        validate_id(activity_id)
        return TokenStore(self.directory/'archive'/activity_id)
    def save(self, activity_id, content, retain_raw=False):
        self.require_enabled()
        if not isinstance(retain_raw,bool):
            raise ValueError('retain_raw_fit must be boolean')
        content = extract(content)
        rows = parse(content)
        store = self.record(activity_id)
        with session_lock(store):
            value = {'activity_id': activity_id, 'source_sha256': hashlib.sha256(content).hexdigest(),
                'archived_at_utc': datetime.now(timezone.utc).isoformat(), 'rows': rows,
                'raw_fit_retained': retain_raw}
            if retain_raw:
                value['raw_fit_base64'] = base64.b64encode(content).decode()
            store.save(json.dumps(value, allow_nan=False))
        return {key: value[key] for key in ('activity_id','source_sha256','archived_at_utc','raw_fit_retained')} | {'sample_count':len(rows)}
    def list(self, limit=20, cursor=0):
        self.require_enabled()
        if isinstance(limit,bool) or isinstance(cursor,bool) or not 1<=limit<=50 or not 0<=cursor<=10000:
            raise ValueError("Use limit 1-50 and cursor 0-10000")
        root=self.directory/'archive'
        if root.is_symlink() or root.is_junction():
            raise ValueError("Archive paths cannot be symlinks")
        ids=sorted((p.name for p in root.iterdir() if p.is_dir() and p.name.isascii() and p.name.isdigit()),key=int) if root.exists() else []
        rows=[]
        for activity_id in ids[cursor:cursor+limit]:
            store=self.record(activity_id)
            if not store.exists(): continue
            value=json.loads(store.load())
            rows.append({key:value[key] for key in ('activity_id','archived_at_utc','source_sha256','raw_fit_retained')})
        return {'activities':rows,'next_cursor':cursor+limit if len(ids)>cursor+limit else None,'local_only':True}

    def analysis(self, activity_id):
        self.require_enabled()
        store = self.record(activity_id)
        if not store.exists():
            raise RequestError('ARCHIVE_NOT_FOUND')
        from .analytics import analyse
        value = json.loads(store.load())
        return {'activity_id':activity_id,'source_sha256':value['source_sha256'],
            'archived_at_utc':value['archived_at_utc'], 'raw_fit_retained':value['raw_fit_retained'],
            **analyse(value['rows'])}


def download(client, directory, activity_id, retain_raw_fit=False):
    from garminconnect import Garmin
    archive = Archive(directory)
    archive.require_enabled()  # Before download, even when called directly by worker.
    validate_id(activity_id)
    return archive.save(activity_id, client.download_activity(activity_id,Garmin.ActivityDownloadFormat.ORIGINAL),retain_raw_fit)


def main():
    import argparse
    from .auth import data_directory
    parser=argparse.ArgumentParser(description="Local archive opt-in; raw FIT retention is separate per recording")
    parser.add_argument("command",choices=["enable","disable","status"])
    args=parser.parse_args()
    archive=Archive(data_directory())
    if args.command!="status":
        archive.settings.save(json.dumps({"enabled":args.command=="enable"}))
    print(json.dumps({"enabled":archive.settings.exists() and json.loads(archive.settings.load()).get("enabled") is True,
        "raw_fit_default":False,"storage":"Windows DPAPI; Linux owner-only files unless optional protected storage enabled"}))


if __name__=="__main__": main()
