"""Synthetic native nap DTO/route acceptance and midnight/overlap rejection."""
import copy
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from garmin_connect_mcp import nap_writes as nw
from garmin_connect_mcp.writes import WriteInputError, WriteService, execute, validate
from test_sleep_writes import Client as SleepClient

DAY = "2026-10-17"


class Client(SleepClient):
    def __init__(self):
        super().__init__()
        self.row.update(sleepStartTimestampGMT=nw.epoch("2026-10-17T06:00:00"),
                        sleepEndTimestampGMT=nw.epoch("2026-10-17T14:30:00"))
        self.naps = [{"userProfilePK": 123, "deviceId": 55, "calendarDate": DAY,
                      "napTimeSec": 1800, "napStartTimestampGMT": "2026-10-17T19:00:00",
                      "napEndTimestampGMT": "2026-10-17T19:30:00", "napStartTimeOffset": -420,
                      "napEndTimeOffset": -420, "napSource": 0, "napFeedback": "original"}]

    def connectapi(self, path, params):
        if "/naps/" in path:
            assert path == nw.BASE + "/naps/" + DAY
            assert params == {"includeOverlaps": True}
            return copy.deepcopy(self.naps)
        return super().connectapi(path, params)

    def request(self, method, domain, path, **kwargs):
        assert domain == "connectapi"
        self.mutations.append((method, path, copy.deepcopy(kwargs)))
        if self.fail:
            raise TimeoutError()
        if not self.mismatch:
            if method in {"PUT", "DELETE"}:
                original_start = int(path.split("/")[5])
                self.naps = [r for r in self.naps if nw.epoch(r["napStartTimestampGMT"]) != original_start]
            if method != "DELETE":
                self.naps.append(copy.deepcopy(kwargs["json"]))
        return SimpleNamespace(raise_for_status=lambda: None)


@pytest.fixture(autouse=True)
def current_time(monkeypatch):
    monkeypatch.setattr(nw, "now", lambda: datetime(2026, 10, 17, 23, tzinfo=timezone.utc))


def parameters(client, operation):
    target = nw.mutation_target(client, DAY, "America/Los_Angeles")
    result = {k: target[k] for k in ("calendar_date", "time_zone", "expected_content_sha256")}
    if operation != "add_nap":
        result["nap_start_ms"] = target["naps"][0]["nap_start_ms"]
    if operation != "delete_nap":
        result.update(start_time="2026-10-17T14:00:00-07:00", end_time="2026-10-17T14:30:00-07:00")
    else:
        result["confirm_delete"] = True
    return result


@pytest.mark.parametrize("operation", nw.OPERATIONS)
def test_guarded_nap_writes_native_identity_body_and_replay(tmp_path, operation):
    client = Client()
    old = copy.deepcopy(client.naps[0])
    p = parameters(client, operation)
    draft = WriteService(tmp_path).prepare(operation, p, "nap-fixture-intent")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "completed", result
    assert result["verification"]["state"] == "stored_value_verified"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1
    method, path, kwargs = client.mutations[0]
    if operation != "add_nap":
        assert f"/{DAY}/{nw.epoch(old['napStartTimestampGMT'])}" in path
    if operation == "update_nap":
        assert path.endswith("/" + str(nw.epoch(old["napEndTimestampGMT"])))
        assert kwargs["json"]["deviceId"] == 55
        assert kwargs["json"]["napFeedback"] == "original"
    if operation != "delete_nap":
        assert kwargs["json"]["napStartTimestampGMT"] == "2026-10-17T21:00:00"
        assert kwargs["json"]["napStartTimeOffset"] == -420
        assert kwargs["json"]["napSource"] == 2
        assert kwargs["json"]["napTimeSec"] == 1800


@pytest.mark.parametrize("patch", [
    {"end_time": "2026-10-17T14:04:59-07:00"},
    {"end_time": "2026-10-17T17:00:01-07:00"},
    {"calendar_date": "2026-10-16"},
    {"start_time": "2026-10-16T23:30:00-07:00"},
    {"napTimeSec": 999}, {"userProfilePK": 999},
])
def test_invalid_nap_inputs(patch):
    p = parameters(Client(), "add_nap")
    p.update(patch)
    with pytest.raises(WriteInputError):
        validate("add_nap", p)


@pytest.mark.parametrize("case", ["stale", "overlap_nap", "overlap_sleep", "midnight"])
def test_preflight_rejects_without_mutation(tmp_path, monkeypatch, case):
    client = Client()
    p = parameters(client, "add_nap")
    if case == "overlap_nap":
        p.update(start_time="2026-10-17T12:15:00-07:00", end_time="2026-10-17T12:45:00-07:00")
    elif case == "overlap_sleep":
        p.update(start_time="2026-10-17T07:00:00-07:00", end_time="2026-10-17T08:00:00-07:00")
    draft = WriteService(tmp_path).prepare("add_nap", p, "nap-preflight-intent")
    if case == "stale":
        client.naps[0]["napFeedback"] = "changed"
    elif case == "midnight":
        monkeypatch.setattr(nw, "now", lambda: datetime(2026, 10, 18, 8, tzinfo=timezone.utc))
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "rejected", result
    assert result["error"]["garmin_mutation_sent"] is False
    assert client.mutations == []


@pytest.mark.parametrize("failure", ["fail", "mismatch"])
def test_nap_uncertain_results_are_terminal(tmp_path, failure):
    client = Client()
    draft = WriteService(tmp_path).prepare("delete_nap", parameters(client, "delete_nap"), "nap-unknown-intent")
    setattr(client, failure, True)
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "unknown"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1
