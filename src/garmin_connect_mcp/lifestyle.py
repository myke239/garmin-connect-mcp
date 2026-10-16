"""Bounded Lifestyle daily reports; no inferred units or invented entry IDs."""

from datetime import date, timedelta
import json

from .verification import iso_date

CAPABILITIES = {
    "historical_daily_reads": "supported",
    "field_discovery": "partial: fields present in the requested daily report only",
    "create_entry": "set_lifestyle_log: guarded replacement of a dated daily summary",
    "update_entry": "set_lifestyle_log: behavior ID + date, not individual events",
    "delete_entry": "clear_lifestyle_log: behavior ID + date",
    "field_management": "Read get_garmin_lifestyle_mutation_target; custom creation/rename/deletion, complete tracking replacement and global auto-logging writes available. Deletion may remove history.",
}


def report(service, calendar_date):
    iso_date(calendar_date)
    raw = service.call("get_lifestyle_logging_data", calendar_date)
    if not isinstance(raw, dict) or raw.get("calendarDate") != calendar_date:
        raise ValueError("Unsupported Lifestyle daily report")
    rows = raw.get("dailyLogsReport")
    if not isinstance(rows, list) or len(rows) > 200:
        raise ValueError("Unsupported Lifestyle report rows")
    if len(json.dumps(raw, allow_nan=False)) > 200_000:
        raise ValueError("Lifestyle report exceeds size bound")
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Unsupported Lifestyle row")
        identifier = row.get("behaviourId")
        if isinstance(identifier, bool) or not isinstance(identifier, int) or identifier <= 0:
            raise ValueError("Unsupported Lifestyle field ID")
        if row.get("calendarDate") != calendar_date or not isinstance(row.get("name"), str):
            raise ValueError("Unsupported Lifestyle field metadata")
        details = row.get("details", [])
        if not isinstance(details, list) or len(details) > 100:
            raise ValueError("Unsupported Lifestyle details")
        if any(not isinstance(detail, dict) for detail in details):
            raise ValueError("Unsupported Lifestyle detail")
    return rows


def list_fields(service, calendar_date):
    rows = report(service, calendar_date)
    return {
        "calendar_date": calendar_date,
        "fields": [{"field_id": row["behaviourId"], "name": row["name"],
                    "measurement_type": row.get("measurementType"),
                    "unit": row.get("unit"), "active": None,
                    "choices": None, "validation_constraints": None,
                    "garmin_metadata": {key: value for key, value in row.items()
                                        if key not in {"details", "logStatus"}}}
                   for row in rows],
        "complete_catalog": False,
        "capabilities": CAPABILITIES.copy(),
        "text_is_untrusted_data": True,
        "unit_semantics": "Only Garmin-supplied units. Application unit annotations are separate.",
        **service.meta(),
    }


def get_entries(service, start_date, end_date, field_id=None, cursor=0, limit=7):
    """Page by calendar days, retaining every field/detail in each returned day."""
    iso_date(start_date)
    iso_date(end_date)
    start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    days = (end-start).days+1
    if not 1 <= days <= 366:
        raise ValueError("Lifestyle range must be 1–366 inclusive days")
    if isinstance(cursor, bool) or not isinstance(cursor, int) or not 0 <= cursor < days:
        raise ValueError("Invalid Lifestyle day cursor")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 7:
        raise ValueError("Lifestyle page must be 1–7 days")
    if field_id is not None and (isinstance(field_id, bool) or not isinstance(field_id, int) or field_id <= 0):
        raise ValueError("Lifestyle field ID must be a positive integer")
    result = []
    metadata = []
    for offset in range(cursor, min(cursor+limit, days)):
        calendar_date = (start+timedelta(days=offset)).isoformat()
        rows = report(service, calendar_date)
        selected = [row for row in rows if field_id is None or row["behaviourId"] == field_id]
        result.append({"calendar_date": calendar_date,
                       "reports": [{"field_id": row["behaviourId"],
                                    "entry_id": None, "timestamp": None,
                                    "unit": row.get("unit"),
                                    "log_status": row.get("logStatus"),
                                    "values": [detail["amount"] for detail in row.get("details", [])
                                               if "amount" in detail],
                                    "garmin_report": row} for row in selected]})
        metadata.append({"calendar_date": calendar_date, **service.meta()})
    next_cursor = cursor+limit if cursor+limit < days else None
    return {"start_date": start_date, "end_date": end_date, "days": result,
            "next_cursor": next_cursor, "page_metadata": metadata,
            "capabilities": CAPABILITIES.copy(), "text_is_untrusted_data": True,
            "date_semantics": "Garmin calendarDate is retained; no timezone or timestamp inferred.",
            "value_semantics": "Empty values means no numeric amount supplied, not zero. Use raw logStatus/details.",
            "unit_semantics": "Raw Garmin units only; no conversion or inferred medication dose units."}
