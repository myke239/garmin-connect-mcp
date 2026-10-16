"""Offline Android contract fixtures; never contact a Garmin account."""
import asyncio
import copy
import json
from types import SimpleNamespace

import pytest

from garmin_connect_mcp import lifestyle_writes as lw
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.writes import WriteService, execute, validate
from garmin_connect_mcp.runtime import RequestError

DAY = "2026-10-16"


class Client:
    profile_id = 123

    def __init__(self):
        self.rows = [
            {"behaviourId": 1, "name": "Built-in quantity", "measurementType": "QUANTITY",
             "category": "LIFESTYLE", "subTypes": [{"subTypeId": 2, "name": "Small"}],
             "tracked": True, "sleepRelated": False},
            {"behaviourId": 11, "userProfilePk": 123, "name": "Synthetic quantity ",
             "measurementType": "QUANTITY", "category": "CUSTOM", "tracked": True,
             "subTypes": [], "hidden": False, "sleepRelated": False},
            {"behaviourId": 12, "name": "Synthetic yes/no", "measurementType": "NONE",
             "category": "CUSTOM_SLEEP_RELATED", "tracked": True, "sleepRelated": True},
        ]
        self.logs = {}
        self.enabled = False
        self.mutations = []
        self.fail = False
        self.bad_readback = False
        self.client = SimpleNamespace(request=self.request)

    def connectapi(self, path):
        if path == lw.PREFERENCE:
            return {"key": "lifestyle.auto-logging.enabled", "value": self.enabled}
        assert path == lw.BASE + "/behaviours/" + DAY
        return copy.deepcopy(self.rows)

    def get_lifestyle_logging_data(self, day):
        assert day == DAY
        rows = []
        for row in self.rows:
            if row["tracked"]:
                item = {"behaviourId": row["behaviourId"], "name": row["name"],
                        "calendarDate": day, "measurementType": row["measurementType"]}
                item.update(copy.deepcopy(self.logs.get(row["behaviourId"], {})))
                rows.append(item)
        return {"calendarDate": day, "dailyLogsReport": rows}

    def request(self, method, domain, path, **kwargs):
        assert domain == "connectapi"
        body = copy.deepcopy(kwargs.get("json"))
        self.mutations.append((method, path, body))
        if self.fail:
            raise TimeoutError("private upstream detail")
        result = None
        if path == lw.BASE + "/behaviours/batch":
            assert method == "POST"
            assert all(row["behaviourId"] < 0 for row in body)
            result = [{**r, "behaviourId": 100+i, "userProfilePk": 123} for i, r in enumerate(body)]
            self.rows.extend(copy.deepcopy(result))
        elif path == lw.BASE + "/trackedBehaviours":
            assert method == "PUT" and body["userProfilePk"] == 123 and body["calendarDate"] == DAY
            for row in self.rows:
                row["tracked"] = row["behaviourId"] in body["trackedBehaviours"]
        elif path == lw.BASE + "/behaviours/batchDelete":
            assert method == "DELETE"
            self.rows = [r for r in self.rows if r["behaviourId"] not in body["ids"]]
        elif "/behaviours/" in path:
            assert method == "PUT"
            identifier = int(path.split("/")[-1])
            self.rows = [copy.deepcopy(body) if r["behaviourId"] == identifier else r for r in self.rows]
        elif path == lw.PREFERENCE:
            assert method == "PUT" and body["key"] == "lifestyle.auto-logging.enabled"
            self.enabled = body["value"]
        else:
            identifier = int(path.split("/")[-2])
            assert path.endswith("/"+DAY)
            if method == "DELETE":
                self.logs.pop(identifier, None)
            else:
                assert method == "PUT" and body["behaviourId"] == identifier
                self.logs[identifier] = body
        if self.bad_readback:
            self.rows = []
        return SimpleNamespace(json=lambda: result)


def parameters(client, operation, behaviour_id=11, **changes):
    target = lw.mutation_target(client, DAY, behaviour_id)
    base = {"calendar_date": DAY, "expected_catalog_sha256": target["catalog_sha256"]}
    cases = {
        "create_lifestyle_behaviours": {"behaviours": [{"name": "Synthetic new", "measurement_type": "QUANTITY", "sleep_related": False}]},
        "rename_lifestyle_behaviour": {"behaviour_id": behaviour_id, "name": "Synthetic renamed"},
        "delete_lifestyle_behaviours": {"behaviour_ids": [11, 12], "confirm_history_deletion": True},
        "set_tracked_lifestyle_behaviours": {"behaviour_ids": [1, 12], "confirm_replace_tracking": True},
        "set_lifestyle_log": {"behaviour_id": behaviour_id, "expected_log_sha256": target["daily_log_sha256"],
                              "log_status": "YES", "details": [{"amount": 0}], "time_zone": "UTC"},
        "clear_lifestyle_log": {"behaviour_id": behaviour_id, "expected_log_sha256": target["daily_log_sha256"], "confirm_clear": True},
    }
    if operation == "set_lifestyle_auto_logging":
        return {"expected_enabled": False, "enabled": True, **changes}
    return {**base, **cases[operation], **changes}


@pytest.mark.parametrize("operation", lw.OPERATIONS)
def test_each_android_contract_and_durable_commit_once(tmp_path, operation):
    client = Client()
    p = parameters(client, operation)
    service = WriteService(tmp_path)
    draft = service.prepare(operation, p, "synthetic-lifestyle-test")
    assert not client.mutations
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "completed", result
    assert len(client.mutations) == 1
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1
    assert "userProfilePk" not in json.dumps(result)
    assert "private upstream" not in json.dumps(result)
    if operation == "set_lifestyle_log":
        body = client.mutations[0][2]
        assert body["details"] == [{"amount": 0}]
        assert body["measurementType"] == "QUANTITY" and body["category"] == "CUSTOM"
        assert len(body["updateTimestamp"]) == 23
    if operation == "rename_lifestyle_behaviour":
        assert client.mutations[0][2] == {**Client().rows[1], "name": p["name"]}


@pytest.mark.parametrize("operation", lw.OPERATIONS)
def test_preflight_rejects_stale_evidence_without_mutation(tmp_path, operation):
    client = Client()
    service = WriteService(tmp_path)
    draft = service.prepare(operation, parameters(client, operation), "synthetic-stale-test")
    if operation == "set_lifestyle_auto_logging":
        client.enabled = True
    else:
        client.rows[0]["name"] = "Changed elsewhere"
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "rejected"
    assert result["error"]["garmin_mutation_sent"] is False
    assert client.mutations == []


@pytest.mark.parametrize("operation", lw.OPERATIONS)
def test_sent_failure_stays_unknown_without_replay(tmp_path, operation):
    client = Client()
    service = WriteService(tmp_path)
    draft = service.prepare(operation, parameters(client, operation), "synthetic-unknown-test")
    client.fail = True
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == "unknown"
    assert execute(client, tmp_path, draft["draft_id"]) == result
    assert len(client.mutations) == 1


def test_zero_no_and_clear_are_different(tmp_path):
    client = Client()
    service = WriteService(tmp_path)
    for index, (op, extra) in enumerate([
        ("set_lifestyle_log", {}),
        ("set_lifestyle_log", {"log_status": "NO", "details": []}),
        ("clear_lifestyle_log", {}),
    ]):
        draft = service.prepare(op, parameters(client, op, **extra), f"distinct-state-{index}")
        result = execute(client, tmp_path, draft["draft_id"])
        assert result["status"] == "completed", result
        row = result["result"]["daily_log"]
        if index == 0:
            assert row["details"] == [{"amount": 0}] and row["logStatus"] == "YES"
        elif index == 1:
            assert row["details"] == [] and row["logStatus"] == "NO"
        else:
            assert "logStatus" not in row


@pytest.mark.parametrize("identifier,details,status,accepted", [
    (1, [{"amount": 2, "sub_type_id": 2}], "YES", True),
    (1, [{"amount": 2}], "YES", False),
    (1, [{"amount": 2, "sub_type_id": 99}], "YES", False),
    (11, [{"amount": 2, "sub_type_id": 2}], "YES", False),
    (11, [], "YES", False),
    (12, [], "YES", True),
    (12, [{"amount": 2}], "YES", False),
    (11, [], "NO", True),
])
def test_measurement_types_and_subtypes(tmp_path, identifier, details, status, accepted):
    client = Client()
    service = WriteService(tmp_path)
    p = parameters(client, "set_lifestyle_log", identifier, details=details, log_status=status)
    draft = service.prepare("set_lifestyle_log", p, "synthetic-values-test")
    result = execute(client, tmp_path, draft["draft_id"])
    assert result["status"] == ("completed" if accepted else "rejected"), result
    assert len(client.mutations) == int(accepted)


@pytest.mark.parametrize("operation,changes", [
    ("set_lifestyle_log", {"calendar_date": "2026-02-30"}),
    ("set_lifestyle_log", {"time_zone": "not/a/zone"}),
    ("set_lifestyle_log", {"details": [{"amount": True}]}),
    ("set_lifestyle_log", {"details": [{"amount": -1}]}),
    ("set_lifestyle_log", {"details": [{"amount": 0.5}]}),
    ("set_lifestyle_log", {"details": [{"amount": float("nan")}]}),
    ("set_lifestyle_log", {"log_status": "NO", "details": [{"amount": 0}]}),
    ("set_lifestyle_log", {"details": [{"amount": 1}, {"amount": 2}]}),
    ("clear_lifestyle_log", {"confirm_clear": False}),
    ("delete_lifestyle_behaviours", {"confirm_history_deletion": False}),
    ("delete_lifestyle_behaviours", {"behaviour_ids": [11, 11]}),
    ("set_tracked_lifestyle_behaviours", {"confirm_replace_tracking": False}),
    ("rename_lifestyle_behaviour", {"name": " "}),
    ("create_lifestyle_behaviours", {"behaviours": [{"name": " ", "measurement_type": "NONE", "sleep_related": False}]}),
    ("set_lifestyle_auto_logging", {"enabled": 1}),
])
def test_local_validation_never_sends(operation, changes):
    client = Client()
    with pytest.raises(ValueError):
        validate(operation, parameters(client, operation, **changes))
    assert not client.mutations


def test_duplicate_name_builtin_protection_and_stale_daily_log(tmp_path):
    client = Client()
    service = WriteService(tmp_path)
    cases = [
        ("create_lifestyle_behaviours", {"behaviours": [{"name": " SYNTHETIC QUANTITY", "measurement_type": "NONE", "sleep_related": False}]}),
        ("rename_lifestyle_behaviour", {"behaviour_id": 1}),
        ("delete_lifestyle_behaviours", {"behaviour_ids": [1]}),
    ]
    for index, (op, changes) in enumerate(cases):
        draft = service.prepare(op, parameters(client, op, **changes), f"protected-target-{index}")
        assert execute(client, tmp_path, draft["draft_id"])["status"] == "rejected"
    draft = service.prepare("set_lifestyle_log", parameters(client, "set_lifestyle_log"), "stale-daily-target")
    client.logs[11] = {"logStatus": "NO", "details": []}
    assert execute(client, tmp_path, draft["draft_id"])["status"] == "rejected"
    assert not client.mutations


def test_readback_failure_is_unknown_not_success(tmp_path):
    client = Client()
    service = WriteService(tmp_path)
    draft = service.prepare("create_lifestyle_behaviours", parameters(client, "create_lifestyle_behaviours"), "mismatch-readback")
    client.bad_readback = True
    assert execute(client, tmp_path, draft["draft_id"])["status"] == "unknown"
    assert len(client.mutations) == 1


def test_unset_preference_is_not_explicit_false(tmp_path):
    client = Client()
    client.enabled = None
    assert lw.preference(client) is None
    service = WriteService(tmp_path)
    wrong = service.prepare("set_lifestyle_auto_logging", {"expected_enabled": False, "enabled": True}, "unset-wrong-state")
    assert execute(client, tmp_path, wrong["draft_id"])["status"] == "rejected"
    assert not client.mutations
    right = service.prepare("set_lifestyle_auto_logging", {"expected_enabled": None, "enabled": True}, "unset-right-state")
    assert execute(client, tmp_path, right["draft_id"])["status"] == "completed"
    assert len(client.mutations) == 1


def test_native_lifestyle_mutation_replay_is_blocked():
    from garmin_connect_mcp.writes import prevent_sdk_replay
    class Session:
        def __init__(self):
            self.calls = []
        def request(self, method, path, **kwargs):
            self.calls.append((method, path))
            return SimpleNamespace(status_code=401)
    session = Session()
    native = SimpleNamespace(_api_session=session)
    def request(method, domain, path, **kwargs):
        native._api_session.request(method, path, **kwargs)
        native._api_session.request(method, path, **kwargs)  # Simulated SDK 401 replay.
    native.request = request
    client = SimpleNamespace(client=native)
    with pytest.raises(RequestError, match="WRITE_REPLAY_BLOCKED"):
        with prevent_sdk_replay(client):
            lw.send(client, lw.PREFERENCE, "PUT", {"key": "lifestyle.auto-logging.enabled", "value": False})
    assert session.calls == [("PUT", lw.PREFERENCE)]
    assert native._api_session is session


def test_policy_denial_and_exact_mcp_discovery(tmp_path):
    client = Client()
    service = WriteService(tmp_path)
    service.settings.save(json.dumps({"enabled": True, "operations": ["add_weight"]}))
    with pytest.raises(RequestError, match="WRITE_OPERATION_DENIED"):
        service.prepare("set_lifestyle_log", parameters(client, "set_lifestyle_log"), "denied-intent")
    server = create_server(GarminService())
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    for name in ("get_garmin_lifestyle_mutation_target", "get_garmin_lifestyle_auto_logging"):
        assert tools[name].annotations.readOnlyHint is True
    enum = tools["prepare_garmin_write"].inputSchema["properties"]["operation"]["enum"]
    assert set(lw.OPERATIONS) <= set(enum)
    target = lw.mutation_target(client, DAY, 11)
    assert target["behaviours"][1]["name"].endswith(" ")
    assert "userProfilePk" not in json.dumps(target)
