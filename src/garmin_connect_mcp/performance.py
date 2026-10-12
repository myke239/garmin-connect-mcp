"""Compact activity analysis with explicit units and coverage."""
from .data import number


def zone_times(raw):
    if not isinstance(raw, list):
        if isinstance(raw, dict):
            raw = raw.get("heartRateZones", raw.get("zones", []))
        else:
            raise ValueError("Unsupported heart-rate zone response")
    rows = []
    for item in raw[:10]:
        if not isinstance(item, dict):
            continue
        rows.append({key: number(item.get(key)) for key in
            ("zoneNumber", "secsInZone", "zoneLowBoundary", "zoneHighBoundary")})
    return {"available": bool(rows), "zones": rows, "units": "secsInZone is seconds; boundaries bpm"}
