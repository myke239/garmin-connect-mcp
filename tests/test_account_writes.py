"""Exact deletion identities, signed corrections and durable failure evidence."""
import copy
from types import SimpleNamespace

import pytest
from garminconnect import Garmin

from garmin_connect_mcp import account_writes as aw
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.writes import WriteInputError, WriteService, execute, validate

DAY = "2026-10-17"


class Client:
    def __init__(self):
        self.weight = [{"samplePk": 1001, "calendarDate": DAY, "weight": 80000, "bodyFat": 20},
                       {"samplePk": 1002, "calendarDate": DAY, "weight": 81000}]
        self.bp = [{"version": 2001, "calendarDate": DAY, "systolic": 120, "diastolic": 80, "notes": "private"},
                   {"version": 2002, "calendarDate": DAY, "systolic": 121, "diastolic": 81}]
        self.total = {"valueInML": 500, "calendarDate": DAY}
        self.activity = {"activityId": 42, "activityName": "Synthetic", "summaryDTO": {"duration": 60}}
        self.mutations = []
        self.fail = False
        self.mismatch = False
        self.client = SimpleNamespace(request=self.request, put=self.put)
        self.garmin_connect_set_hydration_url = Garmin().garmin_connect_set_hydration_url
        self.add_hydration_data = Garmin.add_hydration_data.__get__(self)

    def get_daily_weigh_ins(self, day):
        assert day == DAY
        return {"dateWeightList": copy.deepcopy(self.weight)}

    def get_blood_pressure(self, start, end):
        assert start == end == DAY
        return {"measurementSummaries": [{"measurements": copy.deepcopy(self.bp)}]}

    def get_hydration_data(self, day):
        assert day == DAY
        return copy.deepcopy(self.total)

    def get_activity(self, identity):
        assert str(identity) == "42"
        if self.activity is None:
            raise RequestError("NOT_FOUND")
        return copy.deepcopy(self.activity)

    def put(self, domain, path, **kwargs):
        return self.request("PUT", domain, path, **kwargs)

    def request(self, method, domain, path, **kwargs):
        assert domain == "connectapi"
        self.mutations.append((method, path, copy.deepcopy(kwargs)))
        if self.fail:
            raise TimeoutError()
        if not self.mismatch:
            if path.startswith("/weight-service/"):
                self.weight = [r for r in self.weight if str(r["samplePk"]) != path.split("/")[-1]]
            elif path.startswith("/bloodpressure-service/"):
                self.bp = [r for r in self.bp if str(r["version"]) != path.split("/")[-1]]
            elif path.startswith("/activity-service/"):
                self.activity = None
            else:
                assert path == self.garmin_connect_set_hydration_url
                body = kwargs["json"]
                assert body["calendarDate"] == DAY
                assert body["timestampLocal"].startswith(DAY + "T12:00:00")
                self.total["valueInML"] += body["valueInML"]
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {})


def parameters(client, operation):
    if operation == "delete_activity":
        t = aw.mutation_target(client, "activity", record_id="42")
        return {"activity_id": 42, "expected_name": "Synthetic", "expected_content_sha256": t["expected_content_sha256"], "confirm_delete": True}
    kind = {"delete_weight_measurement": "weight", "delete_blood_pressure_measurement": "blood_pressure",
            "adjust_hydration": "hydration"}[operation]
    t = aw.mutation_target(client, kind, DAY)
    if kind == "hydration":
        return {"calendar_date": DAY, "expected_content_sha256": t["expected_content_sha256"],
                "timestamp": DAY + "T12:00:00-07:00", "value_in_ml": -250}
    return {"calendar_date": DAY, **{k: t["records"][0][k] for k in ("record_id", "expected_content_sha256")}, "confirm_delete": True}


@pytest.mark.parametrize("operation", aw.OPERATIONS)
def test_exact_native_transport_readback_and_idempotence(tmp_path, operation):
    client = Client()
    draft = WriteService(tmp_path).prepare(operation, parameters(client, operation), "account-fixture-intent")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "completed", result
    assert result["verification"]["state"] == "stored_value_verified"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1
    if operation == "delete_weight_measurement":
        assert client.weight == [{"samplePk": 1002, "calendarDate": DAY, "weight": 81000}]
        assert client.mutations[0][1] == "/weight-service/weight/2026-10-17/byversion/1001"
    elif operation == "delete_blood_pressure_measurement":
        assert [r["version"] for r in client.bp] == [2002]
        assert client.mutations[0][1] == "/bloodpressure-service/bloodpressure/2026-10-17/2001"
    elif operation == "adjust_hydration":
        assert client.total["valueInML"] == 250


@pytest.mark.parametrize("operation", aw.OPERATIONS)
def test_stale_records_rejected_before_send(tmp_path, operation):
    client = Client()
    draft = WriteService(tmp_path).prepare(operation, parameters(client, operation), "stale-account-intent")
    client.weight[0]["weight"] += 1
    client.bp[0]["systolic"] += 1
    client.total["valueInML"] += 1
    client.activity["activityName"] = "Changed"
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "rejected"
    assert result["error"]["garmin_mutation_sent"] is False
    assert client.mutations == []


@pytest.mark.parametrize("operation", aw.OPERATIONS)
@pytest.mark.parametrize("failure", ["fail", "mismatch"])
def test_unknown_never_repeats(tmp_path, operation, failure):
    client = Client()
    draft = WriteService(tmp_path).prepare(operation, parameters(client, operation), "unknown-account-intent")
    setattr(client, failure, True)
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "unknown", result
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1


@pytest.mark.parametrize("value", [0, True, 10001, -10001, float("nan")])
def test_hydration_rejects_invalid_deltas(value):
    p = parameters(Client(), "adjust_hydration")
    p["value_in_ml"] = value
    with pytest.raises(WriteInputError):
        validate("adjust_hydration", p)


def test_hydration_cannot_produce_negative_total(tmp_path):
    client = Client()
    p = parameters(client, "adjust_hydration")
    p["value_in_ml"] = -501
    draft = WriteService(tmp_path).prepare("adjust_hydration", p, "negative-total-intent")
    assert execute(client, tmp_path, draft["draft_id"])["status"] == "rejected"
    assert client.mutations == []


def test_bp_target_excludes_notes_and_rejects_missing_exact_version():
    client = Client()
    t = aw.mutation_target(client, "blood_pressure", DAY)
    assert "notes" not in t["records"][0]["record"]
    del client.bp[0]["version"]
    with pytest.raises(ValueError):
        aw.mutation_target(client, "blood_pressure", DAY)


def test_missing_hydration_total_is_unavailable_not_zero(tmp_path):
    client = Client()
    client.total["valueInML"] = None
    target = aw.mutation_target(client, "hydration", DAY)
    assert target["value_in_ml"] is None
    assert target["correction_available"] is False and target["operations"] == []
    draft = WriteService(tmp_path).prepare("adjust_hydration", parameters(client, "adjust_hydration"), "missing-hydration-total")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "rejected"
    assert result["error"]["code"] == "HYDRATION_TOTAL_UNAVAILABLE"
    assert client.mutations == []


def test_hydration_date_binding():
    client = Client()
    client.total["calendarDate"] = "2026-10-16"
    with pytest.raises(ValueError):
        aw.mutation_target(client, "hydration", DAY)
