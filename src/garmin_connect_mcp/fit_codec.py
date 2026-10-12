"""Small private FIT codec worker; official SDK is installed by each user, never bundled."""
import base64
import json
import math
import sys
from datetime import datetime


def decode(content):
    from garmin_fit_sdk import Decoder,Stream
    count=0
    def listener(kind,value):
        nonlocal count
        count+=1
        if count>100000:raise ValueError('FIT message limit exceeded')
    messages,errors=Decoder(Stream.from_byte_array(bytearray(content))).read(mesg_listener=listener)
    if errors:raise ValueError('Invalid or unsupported FIT content')
    raw=messages.get('record_mesgs',[])
    if len(raw)>50000:raise ValueError('FIT sample limit exceeded')
    def number(value):return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) else None
    rows=[]
    for row in raw:
        stamp=row.get('timestamp')
        if not isinstance(stamp,datetime) or stamp.tzinfo is None:raise ValueError('FIT timestamp requires timezone')
        rows.append({'timestamp_s':stamp.timestamp(),'heart_rate_bpm':number(row.get('heart_rate')),
            'power_w':number(row.get('power')),'cadence_rpm':number(row.get('cadence')),
            'speed_m_s':number(row.get('enhanced_speed',row.get('speed'))),
            'elevation_m':number(row.get('enhanced_altitude',row.get('altitude'))),'distance_m':number(row.get('distance'))})
    return {'file_type':messages.get('file_id_mesgs',[{}])[0].get('type') if messages.get('file_id_mesgs') else None,
        'sessions':len(messages.get('session_mesgs',[])), 'laps':len(messages.get('lap_mesgs',[])),
        'activities':len(messages.get('activity_mesgs',[])),'rows':rows}


def main():
    try:
        raw=json.loads(sys.stdin.read(24*1024*1024))
        content=base64.b64decode(raw['content'],validate=True)
        if len(content)>16*1024*1024:raise ValueError
        result=decode(content)
        sys.stdout.write(json.dumps({'ok':True,'result':result},allow_nan=False))
    except Exception:sys.stdout.write(json.dumps({'ok':False,'error':'FIT content invalid or exceeds supported bounds'}))


if __name__=='__main__':main()
