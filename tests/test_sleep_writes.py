"""Native sleep contract fixtures; no real sleep nights are edited."""
import copy
from types import SimpleNamespace

import pytest

from garmin_connect_mcp import sleep_writes as sw
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.writes import WriteInputError, WriteService, execute, validate


class Client:
    profile_id = 123

    def __init__(self):
        self.row = {"id": 42, "userProfilePK": 123, "calendarDate": "2026-10-17",
                    "sleepStartTimestampGMT": 1792220400000, "sleepEndTimestampGMT": 1792249200000,
                    "sleepStartTimestampLocal": 1792195200000, "sleepEndTimestampLocal": 1792224000000,
                    "sleepTimeSeconds": 28000, "sleepWindowConfirmed": False,
                    "sleepWindowConfirmationType": "auto_confirmed", "deepSleepSeconds": 6000,
                    "sleepScores": {"overall": {"value": 82}}, "userNote": "old"}
        self.mutations = []
        self.client = SimpleNamespace(request=self.request)
        self.fail = False
        self.mismatch = False

    def connectapi(self, path, params):
        assert path == sw.BASE + "/dailySleepData"
        assert params == {"date": "2026-10-17", "nonSleepBufferMinutes": 60}
        return {"dailySleepDTO": copy.deepcopy(self.row)}

    def request(self, method, domain, path, **kwargs):
        assert domain == "connectapi"
        self.mutations.append((method, path, copy.deepcopy(kwargs)))
        if self.fail:
            raise TimeoutError()
        if not self.mismatch:
            if path.endswith("/note"):
                self.row["userNote"] = kwargs["json"]["userNote"] if method == "PUT" else None
            else:
                assert path == sw.BASE + "/dailySleep/42"
                self.row = copy.deepcopy(kwargs["json"])
        return SimpleNamespace(raise_for_status=lambda: None)


def parameters(client, operation):
    target = sw.mutation_target(client, "2026-10-17")
    result = {k: target[k] for k in ("calendar_date", "sleep_id", "expected_content_sha256")}
    if operation == "update_sleep_times":
        result.update(start_time="2026-10-16T23:00:00-07:00", end_time="2026-10-17T07:30:00-07:00",
                      time_zone="America/Los_Angeles")
    elif operation == "set_sleep_note":
        result["note"] = "synthetic fixture"
    return result


@pytest.mark.parametrize("operation", sw.OPERATIONS[1:])
def test_guarded_native_transport_readback_and_replay(tmp_path, operation):
    client = Client()
    original = copy.deepcopy(client.row)
    draft = WriteService(tmp_path).prepare(operation, parameters(client, operation), "synthetic-sleep")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "completed"
    assert result["verification"]["state"] == "stored_value_verified"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1
    if operation == "update_sleep_times":
        assert client.row["sleepTimeSeconds"] == 30600
        assert client.row["sleepWindowConfirmed"] is True
        changed = {k for k in original if original[k] != client.row[k]}
        assert changed <= {"sleepStartTimestampGMT", "sleepEndTimestampGMT", "sleepTimeSeconds", "sleepWindowConfirmed"}
        assert client.row["sleepScores"] == original["sleepScores"]
        assert client.row["deepSleepSeconds"] == 6000
        assert client.row["sleepStartTimestampLocal"] == original["sleepStartTimestampLocal"]


def test_stale_target_rejected_without_mutation(tmp_path):
    client = Client()
    draft = WriteService(tmp_path).prepare("clear_sleep_note", parameters(client, "clear_sleep_note"), "stale-intent")
    client.row["userNote"] = "changed elsewhere"
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "rejected"
    assert result["error"]["code"] == "MUTATION_TARGET_CHANGED"
    assert result["error"]["garmin_mutation_sent"] is False
    assert client.mutations == []


@pytest.mark.parametrize("failure", ["fail", "mismatch"])
def test_unknown_outcomes_are_terminal(tmp_path, failure):
    client = Client()
    draft = WriteService(tmp_path).prepare("clear_sleep_note", parameters(client, "clear_sleep_note"), "uncertain")
    setattr(client, failure, True)
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "unknown"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1


@pytest.mark.parametrize("patch", [
    {"start_time": "2026-10-16T23:00:00"},
    {"end_time": "2026-10-17T07:30:00-08:00"},
    {"start_time": "2026-10-17T08:00:00-07:00"},
    {"calendar_date": "2026-10-16"}, {"time_zone": "invalid"},
    {"sleepScores": {"overall": 99}}, {"deepSleepSeconds": 999},
    {"start_time": "2026-03-08T02:30:00-08:00", "end_time": "2026-03-08T04:30:00-07:00",
     "calendar_date": "2026-03-08"},
])
def test_invalid_inputs_never_prepare(patch):
    value = parameters(Client(), "update_sleep_times")
    value.update(patch)
    with pytest.raises(WriteInputError):
        validate("update_sleep_times", value)


def test_explicit_fallback_offsets_measure_actual_elapsed_duration():
    value = parameters(Client(), "update_sleep_times")
    value.update(calendar_date="2025-11-02", start_time="2025-11-02T01:15:00-07:00",
                 end_time="2025-11-02T01:45:00-08:00")
    assert sw.times(value)[2] == 5400


def test_target_does_not_expose_account_identifier_or_recorded_scores():
    target = sw.mutation_target(Client(), "2026-10-17")
    assert "userProfilePK" not in target["sleep"]
    assert "sleepScores" not in target["sleep"]
    client = Client()
    client.row["userProfilePK"] = 999
    with pytest.raises(ValueError):
        sw.mutation_target(client, "2026-10-17")


def test_manual_sleep_requires_absence_and_uses_native_new_record_defaults(tmp_path):
    class EmptyClient(Client):
        def __init__(self):
            super().__init__()
            self.row = None

        def request(self, method, domain, path, **kwargs):
            assert method == "POST" and path == sw.BASE + "/dailySleep"
            body = copy.deepcopy(kwargs["json"])
            self.mutations.append((method, path, body))
            assert body["id"] == -1 and body["userProfilePK"] == 123
            assert body["calendarDate"] == "2026-10-17"
            assert body["sleepFromDevice"] is False
            assert body["deepSleepSeconds"] == body["remSleepSeconds"] == 0
            assert "sleepScores" not in body
            self.row = {**body, "id": 99, "userProfilePK": 123, "calendarDate": "2026-10-17"}
            return SimpleNamespace(raise_for_status=lambda: None)

    client = EmptyClient()
    target = sw.mutation_target(client, "2026-10-17")
    assert target["sleep_exists"] is False and target["operations"] == ["add_sleep"]
    p = {k: target[k] for k in ("calendar_date", "expected_content_sha256")}
    p.update(start_time="2026-10-16T23:00:00-07:00", end_time="2026-10-17T07:30:00-07:00",
             time_zone="America/Los_Angeles")
    draft = WriteService(tmp_path).prepare("add_sleep", p, "new-sleep-fixture")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "completed", result
    assert result["result"]["sleep_id"] == "99"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1


def test_manual_sleep_never_overwrites_existing_record(tmp_path):
    client = Client()
    p = parameters(client, "update_sleep_times")
    del p["sleep_id"]
    draft = WriteService(tmp_path).prepare("add_sleep", p, "no-overwrite-sleep")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "rejected"
    assert client.mutations == []
