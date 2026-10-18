"""Fixed dispatcher for writes requiring native snapshot preflight/readback."""
from . import account_writes, nap_writes, sleep_writes
from .runtime import RequestError

HANDLERS = {operation: module for module in (account_writes, nap_writes, sleep_writes)
            for operation in module.OPERATIONS}
OPERATIONS = tuple(HANDLERS)


def validate(operation, parameters):
    return HANDLERS[operation].validate(operation, parameters)


def preflight(client, operation, parameters):
    try:
        return HANDLERS[operation].preflight(client, operation, parameters)
    except (ValueError, TypeError, KeyError, IndexError):
        raise RequestError("INVALID_PREFLIGHT_RESPONSE") from None


def perform(client, operation, parameters, state):
    return HANDLERS[operation].perform(client, operation, parameters, state)
