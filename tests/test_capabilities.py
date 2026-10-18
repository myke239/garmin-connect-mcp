"""Offline completeness, policy and evidence semantics for write discovery."""
import asyncio
import json

import pytest

from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.capabilities import RESOURCES, describe
from garmin_connect_mcp.mutation_targets import fingerprint, require_unchanged, verification_result
from garmin_connect_mcp.runtime import RequestError
from garmin_connect_mcp.server import create_server
from garmin_connect_mcp.service import GarminService
from garmin_connect_mcp.writes import OPERATIONS, WriteService


def test_registry_covers_tools_and_operations_without_account_access(tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("Offline discovery contacted Garmin")
    backend = GarminService(TokenStore(tmp_path), runner=forbidden)
    server = create_server(backend)
    tools = asyncio.run(server.list_tools())
    assert {t.name for t in tools} == {n for r in RESOURCES for n in r.reads}
    assert set(OPERATIONS) == {n for r in RESOURCES for n in r.operations}
    prepare = next(t for t in tools if t.name == "prepare_garmin_write")
    assert set(prepare.inputSchema["properties"]["operation"]["enum"]) == set(OPERATIONS)
    result = asyncio.run(server.call_tool("get_garmin_capabilities", {}))
    assert json.loads(result[0].text)["account_request_sent"] is False


def test_capabilities_preserve_policy_profile_and_remote_grant(tmp_path):
    writes = WriteService(tmp_path)
    writes.settings.save(json.dumps({"enabled": True, "operations": ["add_weight"]}))
    result = describe("weight", writes, {"get_garmin_measurements"}, False)
    operation = result["resources"][0]["registered_writes"][0]
    assert operation["allowed_by_local_policy"] is True
    assert operation["commit_exposed_by_profile"] is False
    assert operation["remote_write_grant_present"] is False
    denied = describe("blood_pressure", writes, set(), None)
    assert denied["resources"][0]["registered_writes"][0]["allowed_by_local_policy"] is False
    with pytest.raises(ValueError):
        describe("arbitrary", writes, set(), None)


def test_mutation_target_canonical_bounded_and_sensitive_to_change():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})
    require_unchanged({"a": 1}, fingerprint({"a": 1}))
    with pytest.raises(RequestError, match="MUTATION_TARGET_CHANGED"):
        require_unchanged({"a": 2}, fingerprint({"a": 1}))
    for value in ({"a": float("nan")}, {"a": "x" * 500001}):
        with pytest.raises(ValueError):
            fingerprint(value)


def test_verification_never_confuses_transport_storage_and_device_sync():
    assert verification_result("add_weight", {})["state"] == "transport_accepted"
    assert verification_result("add_weight", {"verified": True}) == {
        "state": "stored_value_verified", "physical_device_sync": "not_verified"}
    assert verification_result("delete_lifestyle_behaviours", {
        "catalog_absence_verified": True})["historical_erasure"] == "not_verified"
