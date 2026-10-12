"""Explicitly synthetic recordings for offline and authorized live audit checks."""
from datetime import datetime,timedelta,timezone


def fit_activity(start=None):
    from garmin_fit_sdk import Encoder,Profile
    start=start or datetime(2000,1,2,12,tzinfo=timezone.utc)
    end=start+timedelta(minutes=1)
    encoder=Encoder()
    encoder.on_mesg(Profile["mesg_num"]["FILE_ID"],{
        "type":"activity","manufacturer":"development","product":1,"time_created":start,"serial_number":123456789})
    for stamp,distance in [(start,0),(end,100)]:
        encoder.on_mesg(Profile["mesg_num"]["RECORD"],{"timestamp":stamp,"distance":distance})
    encoder.on_mesg(Profile["mesg_num"]["LAP"],{"message_index":0,"timestamp":end,"start_time":start,
        "total_elapsed_time":60,"total_timer_time":60,"total_distance":100})
    encoder.on_mesg(Profile["mesg_num"]["SESSION"],{"message_index":0,"timestamp":end,"start_time":start,
        "total_elapsed_time":60,"total_timer_time":60,"total_distance":100,"sport":"walking","sub_sport":"generic",
        "first_lap_index":0,"num_laps":1})
    encoder.on_mesg(Profile["mesg_num"]["ACTIVITY"],{"timestamp":end,"num_sessions":1,"total_timer_time":60})
    return bytes(encoder.close())


def gpx_activity(name,start="2000-01-02T10:00:00Z",end="2000-01-02T10:01:00Z"):
    from xml.sax.saxutils import escape
    return (f'<gpx version="1.1" creator="Garmin MCP authorized audit" xmlns="http://www.topografix.com/GPX/1/1">'
        f'<trk><name>{escape(name)}</name><trkseg><trkpt lat="0" lon="0"><time>{start}</time></trkpt>'
        f'<trkpt lat="0" lon="0.001"><time>{end}</time></trkpt></trkseg></trk></gpx>').encode()


def tcx_activity(name):
    from xml.sax.saxutils import escape
    return (f'<TrainingCenterDatabase xmlns="http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2">'
        '<Activities><Activity Sport="Running"><Id>2000-01-02T11:00:00Z</Id>'
        '<Lap StartTime="2000-01-02T11:00:00Z"><TotalTimeSeconds>60</TotalTimeSeconds>'
        '<DistanceMeters>100</DistanceMeters><Calories>0</Calories><Intensity>Active</Intensity><TriggerMethod>Manual</TriggerMethod>'
        '<Track><Trackpoint><Time>2000-01-02T11:00:00Z</Time><DistanceMeters>0</DistanceMeters></Trackpoint>'
        '<Trackpoint><Time>2000-01-02T11:01:00Z</Time><DistanceMeters>100</DistanceMeters></Trackpoint></Track>'
        f'</Lap><Notes>{escape(name)}</Notes></Activity></Activities></TrainingCenterDatabase>').encode()
