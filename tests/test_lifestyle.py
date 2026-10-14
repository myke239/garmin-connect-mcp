"""Synthetic fixtures only; default tests never access Garmin."""
import asyncio
from copy import deepcopy

import pytest

from garmin_connect_mcp.lifestyle import get_entries, list_fields
from garmin_connect_mcp.runtime import ALLOWED, RequestError
from garmin_connect_mcp.server import create_server, safe_call
from garmin_connect_mcp.service import GarminService


class Service:
    def __init__(self):
        self.calls = []

    def call(self, method, day):
        self.calls.append((method, day))
        return {"calendarDate": day, "dailyLogsReport": [
            {"behaviourId": 10, "name": "Custom quantity", "calendarDate": day,
             "measurementType": "QUANTITY", "logStatus": "YES",
             "details": [{"amount": 15.125}, {"amount": 0}], "futureMetadata": "retained"},
            {"behaviourId": 11, "name": "Custom empty ", "calendarDate": day,
             "measurementType": "QUANTITY"}]}

    def meta(self):
        return {"cached": False, "fetched_at_utc": "synthetic"}


def test_metadata_and_values_without_unit_inference():
    service = Service()
    fields = list_fields(service, "2026-10-14")
    assert fields["complete_catalog"] is False
    assert fields["fields"][1]["name"] == "Custom empty "
    assert fields["fields"][0]["garmin_metadata"]["futureMetadata"] == "retained"
    assert "details" not in fields["fields"][0]["garmin_metadata"]
    records = get_entries(service, "2026-10-14", "2026-10-14")["days"][0]["reports"]
    assert records[0]["values"] == [15.125, 0]
    assert records[1]["values"] == []
    assert records[0]["unit"] is None
    assert records[0]["entry_id"] is None
    assert records[0]["timestamp"] is None


def test_90_day_history_and_field_filter():
    service = Service()
    cursor = 0
    days = []
    while cursor is not None:
        result = get_entries(service, "2026-07-17", "2026-10-14", 10, cursor)
        days.extend(result["days"])
        cursor = result["next_cursor"]
    assert len(days) == 90
    assert len(service.calls) == 90
    assert days[-1]["calendar_date"] == "2026-10-14"
    assert all(len(day["reports"]) == 1 for day in days)
    absent = get_entries(service, "2026-10-14", "2026-10-14", 999)
    assert absent["days"][0]["reports"] == []


@pytest.mark.parametrize("kwargs", [
    {"start_date": "2026-10-15"}, {"end_date": "2028-10-14"},
    {"cursor": -1}, {"cursor": True}, {"cursor": 1}, {"limit": 8},
    {"limit": False}, {"field_id": True}, {"field_id": 0},
    {"start_date": "2026-10-14/../other"},
])
def test_validation_before_account_access(kwargs):
    service = Service()
    params = {"start_date": "2026-10-14", "end_date": "2026-10-14", **kwargs}
    with pytest.raises(ValueError):
        get_entries(service, **params)
    assert service.calls == []


@pytest.mark.parametrize("mutate", [
    lambda raw: raw.update(calendarDate="2026-10-13"),
    lambda raw: raw.update(dailyLogsReport=None),
    lambda raw: raw.update(dailyLogsReport=raw["dailyLogsReport"]*101),
    lambda raw: raw["dailyLogsReport"][0].update(behaviourId=True),
    lambda raw: raw["dailyLogsReport"][0].update(details=[0]),
    lambda raw: raw["dailyLogsReport"][0].update(details=[{}]*101),
    lambda raw: raw["dailyLogsReport"][0].update(details=[{"amount": float("nan")}]),
])
def test_unsupported_or_unbounded_shapes_fail_closed(mutate):
    service = Service()
    raw = deepcopy(service.call("get_lifestyle_logging_data", "2026-10-14"))
    mutate(raw)
    service.call = lambda *args: raw
    result = safe_call(list_fields, service, "2026-10-14")
    assert result["error"]["code"] == "INVALID_INPUT_OR_RESPONSE"


def test_errors_propagate_without_sensitive_values():
    service = Service()
    def fail(*args):
        raise RequestError("RATE_LIMITED")
    service.call = fail
    assert safe_call(get_entries, service, "2026-10-14", "2026-10-14")["error"]["code"] == "RATE_LIMITED"


def test_mcp_discovery_and_worker_allowlist():
    assert "get_lifestyle_logging_data" in ALLOWED
    server = create_server(GarminService(), tool_profile="recovery")
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    for name in ("list_garmin_lifestyle_fields", "get_garmin_lifestyle_entries"):
        assert tools[name].annotations.readOnlyHint is True
    assert "create_garmin_lifestyle_entry" not in tools
