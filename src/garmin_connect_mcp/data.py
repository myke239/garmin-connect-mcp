"""Explicit metric allowlists: Garmin responses never pass through wholesale."""

import math
from datetime import date


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) else None


def activity(raw: dict) -> dict:
    if not isinstance(raw, dict):
        raise ValueError("Invalid activity response")
    summary = raw.get("summaryDTO", raw)
    if not isinstance(summary, dict):
        raise ValueError("Invalid activity summary")
    kind = raw.get("activityTypeDTO", raw.get("activityType", {}))
    kind = kind.get("typeKey") if isinstance(kind, dict) else None
    distance = number(summary.get("distance"))
    duration = number(summary.get("duration"))
    speed = number(summary.get("averageSpeed"))
    return {
        "activity_id": str(raw["activityId"]),
        "name": str(raw.get("activityName", ""))[:500],
        "activity_type": kind,
        "started_at_utc": summary.get("startTimeGMT"),
        "started_at_local": summary.get("startTimeLocal"),
        "distance_m": distance,
        "duration_s": duration,
        "moving_duration_s": number(summary.get("movingDuration")),
        "average_speed_m_s": speed,
        "average_pace_s_km": 1000 / speed if speed and speed > 0 else None,
        "average_heart_rate_bpm": number(summary.get("averageHR")),
        "max_heart_rate_bpm": number(summary.get("maxHR")),
        "elevation_gain_m": number(summary.get("elevationGain")),
        "calories_kcal": number(summary.get("calories")),
        "text_is_untrusted_data": True,
    }


def validate_range(start: str, end: str) -> None:
    first, last = date.fromisoformat(start), date.fromisoformat(end)
    if first.isoformat() != start or last.isoformat() != end or not 0 <= (last-first).days <= 89:
        raise ValueError("Use YYYY-MM-DD with an inclusive range of at most 90 days")


def validate_id(value: str) -> str:
    if not value.isascii() or not value.isdigit() or len(value) > 20 or int(value) <= 0:
        raise ValueError("Activity ID must be a positive decimal integer")
    return value


def splits(raw: dict) -> dict:
    rows = raw.get("lapDTOs")
    if rows is None:
        return {"available": False, "splits": []}
    if not isinstance(rows, list):
        raise ValueError("Invalid splits")
    return {"available": bool(rows), "truncated": len(rows) > 500,
            "splits": [{"lap_index": row.get("lapIndex"),
                        **{k: v for k, v in activity({"activityId": raw["activityId"], **row}).items()
                           if k not in ("name", "activity_type", "text_is_untrusted_data")}}
                       for row in rows[:500]]}


def heart_rate_samples(raw: dict, maximum: int) -> dict:
    descriptors = raw.get("metricDescriptors") or []
    channels = {d.get("key"): d for d in descriptors if isinstance(d, dict)}
    hr = channels.get("directHeartRate")
    if not hr:
        return {"available": False, "samples": []}
    samples = raw.get("activityDetailMetrics") or []
    if not isinstance(samples, list):
        raise ValueError("Invalid sample data")
    def read(values, key):
        descriptor = channels.get(key, {})
        index = descriptor.get("metricsIndex")
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(values):
            return None
        return number(values[index])
    rows = []
    for sample in samples[:10000]:
        values = sample.get("metrics") or []
        rows.append({"timestamp_unix_ms": read(values, "directTimestamp"),
                     "heart_rate_bpm": read(values, "directHeartRate")})
    original = len(rows)
    if len(rows) > maximum:
        rows = [rows[round(i * (len(rows)-1) / (maximum-1))] for i in range(maximum)] if maximum > 1 else rows[:1]
    return {"available": bool(rows), "samples": rows, "returned_points": len(rows),
            "source_points": original, "downsampled": len(rows) < original,
            "server_may_downsample": True}


def strength_sets(raw: dict) -> dict:
    rows = raw.get("exerciseSets")
    if rows is None:
        return {"available": False, "sets": []}
    if not isinstance(rows, list):
        raise ValueError("Invalid strength sets")
    # Retain Garmin's raw weight unit instead of guessing kg vs grams.
    return {"available": bool(rows), "truncated": len(rows) > 500,
            "weight_unit": "garmin_raw_unverified", "sets": [
                {"set_type": str(row.get("setType", ""))[:50],
                 "duration_s": number(row.get("duration")),
                 "repetitions": number(row.get("repetitionCount")),
                 "weight_raw": number(row.get("weight")),
                 "exercises": [{"category": str(e.get("category", ""))[:100],
                                "name": str(e.get("name", ""))[:200]}
                               for e in (row.get("exercises") or [])[:10]],
                 "text_is_untrusted_data": True}
                for row in rows[:500]]}

