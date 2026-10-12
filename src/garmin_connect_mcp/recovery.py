"""Bounded wellness/performance reads; no account identifiers or raw timelines."""
from datetime import datetime, timedelta
from typing import Literal

from .data import number, validate_id
from .verification import iso_date
from .runtime import RequestError

RecoveryKind = Literal["sleep", "hrv", "stress", "body_battery", "readiness", "training_status",
    "vo2_max", "threshold", "race_predictions", "heart_rate_zones", "daily_summary",
    "personal_records"]
METHODS = {"sleep": "get_sleep_data", "hrv": "get_hrv_data", "stress": "get_stress_data",
    "body_battery": "get_body_battery", "readiness": "get_morning_training_readiness",
    "training_status": "get_training_status", "vo2_max": "get_max_metrics",
    "threshold": "get_lactate_threshold", "race_predictions": "get_race_predictions",
    "heart_rate_zones": "get_heart_rate_zones", "daily_summary": "get_stats",
    "personal_records": "get_personal_record"}
UNDATED = {"threshold", "race_predictions", "heart_rate_zones", "personal_records"}
FIELDS = set("""calendarDate date sinceDate timestamp sleepStartTimestampGMT sleepEndTimestampGMT
sleepTimeSeconds napTimeSeconds deepSleepSeconds lightSleepSeconds remSleepSeconds awakeSleepSeconds
unmeasurableSleepSeconds sleepScores overall value qualifierKey weeklyAvg lastNightAvg lastNight5MinHigh
baseline lowUpper balancedLow balancedUpper markerValue status hrvSummary avgStressLevel maxStressLevel
charged drained highestValue lowestValue score level sleepScore recoveryTime acuteLoad hrvWeeklyAverage
inputContext validSleep sleepScoreFactorPercent recoveryTimeFactorPercent acwrFactorPercent
stressHistoryFactorPercent hrvFactorPercent sleepHistoryFactorPercent mostRecentVO2Max generic cycling
vo2MaxPreciseValue vo2MaxValue fitnessAge mostRecentTrainingLoadBalance monthlyLoadAerobicLow
monthlyLoadAerobicHigh monthlyLoadAnaerobic mostRecentTrainingStatus trainingStatus weeklyTrainingLoad
loadTunnelMin loadTunnelMax loadLevelTrend sport subSport fitnessTrend trainingPaused primaryTrainingDevice
acuteTrainingLoadDTO acwrPercent acwrStatus dailyTrainingLoadAcute dailyTrainingLoadChronic
dailyAcuteChronicWorkloadRatio minTrainingLoadChronic maxTrainingLoadChronic speed_and_heart_rate
speed heartRate heartRateCycling power functionalThresholdPower powerToWeight isStale origin
time5K time10K timeHalfMarathon timeMarathon trainingMethod zone1Floor zone2Floor zone3Floor zone4Floor
zone5Floor maxHeartRateUsed lactateThresholdHeartRateUsed restingHeartRateUsed totalSteps
totalKilocalories activeKilocalories bmrKilocalories totalDistanceMeters restingHeartRate
minHeartRate maxHeartRate averageStressLevel lowStressDuration mediumStressDuration highStressDuration
restStressDuration moderateIntensityMinutes vigorousIntensityMinutes typeId value recordDate
personalRecords recordType startDate endDate dateTime sportType""".split())
MAPS = {"metricsTrainingLoadBalanceDTOMap", "latestTrainingStatusData"}


def compact(value, depth=0):
    if depth > 8:
        raise ValueError("Wellness response exceeds nesting limit")
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key in MAPS and isinstance(item, dict):
                # Device IDs are map keys upstream; expose only bounded metric rows.
                result[key] = [compact(row, depth + 1) for row in list(item.values())[:10]]
            elif key in FIELDS:
                result[key] = compact(item, depth + 1)
        return result
    if isinstance(value, list):
        return [compact(row, depth + 1) for row in value[:31]]
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, str):
        return value[:200]
    return number(value)


def meaningful(value):
    if isinstance(value, dict):
        return any(meaningful(item) for key, item in value.items() if key not in {"calendarDate", "date"})
    if isinstance(value, list):
        return any(meaningful(item) for item in value)
    return value is not None


def read_recovery(service, kind, calendar_date):
    if kind not in METHODS:
        raise ValueError("Unsupported wellness/performance kind")
    iso_date(calendar_date)
    raw = service.call(METHODS[kind], *([] if kind in UNDATED else [calendar_date]))
    if kind == "sleep":
        raw = raw.get("dailySleepDTO", {}) if isinstance(raw, dict) else raw
    data = compact(raw)
    return {"kind": kind, "requested_date": calendar_date, "available": meaningful(data),
        "data": data, "truncated_lists_at": 31, "text_is_untrusted_data": True,
        "date_semantics": "Undated kinds return the latest available record; use its calendarDate, not requested_date.",
        "units": {"sleep_durations": "seconds", "hrv": "milliseconds", "heart_rates": "bpm",
            "scores": "Garmin scales; not medical assessments", "race_prediction_times": "seconds",
            "other_fields": "Garmin raw units; never infer CTL/ATL/TSB or recoveryTime units"},
        "morning_context_confirmed": kind == "readiness" and isinstance(data, dict)
            and data.get("inputContext") == "AFTER_WAKEUP_RESET", **service.meta()}


def session_context(service, activity_id, sleep_calendar_date=None):
    result = service.get_activity(validate_id(activity_id))
    start = result["activity"].get("started_at_local")
    if not isinstance(start, str):
        raise ValueError("Activity lacks a local start date; query wellness with an explicit calendar date")
    stamp = datetime.fromisoformat(start.replace("Z", "+00:00"))
    day = stamp.date()
    sleep_day = iso_date(sleep_calendar_date) if sleep_calendar_date else (
        day - timedelta(days=1) if stamp.hour < 4 else day).isoformat()
    fields = {}
    for kind in ("sleep", "hrv", "stress", "body_battery", "readiness", "training_status"):
        try:
            fields[kind] = read_recovery(service, kind, sleep_day if kind in {"sleep", "hrv"} else day.isoformat())
        except RequestError as error:
            if error.code in {"AUTH_REQUIRED", "RATE_LIMITED", "ACCESS_DENIED"}:
                raise
            fields[kind] = {"available": False, "error": {"code": error.code}}
    # Zone endpoint has different named fields; handled in the dedicated normalizer.
    from .performance import zone_times
    return {"activity": result["activity"], "splits": service.get_activity_splits(activity_id),
        "heart_rate_zones": zone_times(service.call("get_activity_hr_in_timezones", activity_id)),
        "context": fields, "sleep_calendar_date": sleep_day,
        "date_semantics": "Sleep uses Garmin's wake-date convention; before 04:00 defaults to the preceding wake date. Override sleep_calendar_date for shift work or an ambiguous night.",
        "guidance": "Missing readings are unavailable, not zero. Readiness may be an unconfirmed first-snapshot fallback. Observations are not medical diagnoses."}
