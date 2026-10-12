"""Bounded, fixed-purpose verification reads; no arbitrary endpoints."""
from datetime import date


def calendar(raw):
    if not isinstance(raw,dict) or not isinstance(raw.get("calendarItems"),list):
        raise ValueError("Unsupported calendar shape")
    entries=[v for v in raw["calendarItems"] if isinstance(v,dict) and v.get("itemType") == "workout"]
    return {"scheduled_workouts":[{k:v for k,v in row.items() if k in {
        "id","groupId","workoutId","title","date","sportTypeKey","itemType","duration","distance"}}
        for row in entries[:500]],"truncated":len(entries)>500,
        "id_semantics":"id is the scheduled calendar entry; groupId/workoutId may identify its template. Verify before unscheduling.",
        "text_is_untrusted_data":True}


def devices(raw):
    if not isinstance(raw,list): raise ValueError("Unsupported device shape")
    return {"devices":[{k:v for k,v in row.items() if k in {
        "deviceId","userDeviceId","displayName","productDisplayName","deviceTypeSimpleName","primary"}}
        for row in raw[:50] if isinstance(row,dict)],"truncated":len(raw)>50,"text_is_untrusted_data":True}


def activity_types(raw):
    if not isinstance(raw,list): raise ValueError("Unsupported activity-type shape")
    return {"activity_types":[{k:v for k,v in row.items() if k in {
        "typeId","typeKey","parentTypeId","isHidden","restricted"}}
        for row in raw[:500] if isinstance(row,dict)],"truncated":len(raw)>500}


def health(raw):
    """Remove account identifiers, notes and unneeded profile/goal data."""
    allowed={"dateWeightList","totalAverage","weight","bmi","bodyFat","bodyWater","boneMass",
        "muscleMass","physiqueRating","visceralFat","metabolicAge","date","samplePk","version",
        "calendarDate","valueInML","lastEntryTimestampLocal","startDate","endDate","from","until",
        "measurementSummaries","measurements","measurementTimestampLocal","measurementTimestampGMT",
        "systolic","diastolic","pulse","timestamp","timestampGMT","timestampLocal","weightPk",
        "bodyComposition","measurementId","bodyFatPercentage","hydrationPercentage","bodyMassIndex"}
    def walk(value,depth=0):
        if depth>6: raise ValueError("Health response nesting exceeds limit")
        if isinstance(value,dict): return {k:walk(v,depth+1) for k,v in value.items() if k in allowed}
        if isinstance(value,list):
            if len(value)>500: raise ValueError("Health response exceeds entry limit")
            return [walk(v,depth+1) for v in value]
        return value
    if not isinstance(raw,dict): raise ValueError("Unsupported health shape")
    return {"measurements":walk(raw),"units":"Garmin raw response units; weight response may be grams. Never assume input and response units match."}


def iso_date(value):
    if not isinstance(value,str) or len(value)!=10 or date.fromisoformat(value).isoformat()!=value:
        raise ValueError("Use YYYY-MM-DD")
    return value
