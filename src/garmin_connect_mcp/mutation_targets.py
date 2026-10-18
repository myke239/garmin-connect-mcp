"""Shared bounded native snapshots; never accept caller-chosen endpoints."""
import hashlib
import json

from .runtime import RequestError


def fingerprint(value):
    serialized = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":"))
    if len(serialized.encode()) > 500_000:
        raise ValueError("Mutation target exceeds size bound")
    return hashlib.sha256(serialized.encode()).hexdigest()


def require_unchanged(value, expected):
    if fingerprint(value) != expected:
        raise RequestError("MUTATION_TARGET_CHANGED")


def verification_result(operation, result):
    """Add truthful evidence to NEW commits; never reinterpret old journal entries."""
    if isinstance(result, dict) and result.get("verified") is True:
        return {"state": "stored_value_verified", "physical_device_sync": "not_verified"}
    if operation == "delete_lifestyle_behaviours" and isinstance(result, dict) and result.get("catalog_absence_verified") is True:
        return {"state": "catalog_absence_verified", "historical_erasure": "not_verified"}
    return {"state": "transport_accepted", "stored_value_readback": "not_checked",
            "guidance": "Read the operation's fresh verification target before claiming stored values or physical sync."}
