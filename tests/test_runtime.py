import time
import threading
import sys
from concurrent.futures import ThreadPoolExecutor

import pytest

from garmin_connect_mcp.auth import TokenStore
from garmin_connect_mcp.runtime import RequestError, execute_worker, error_code
from garmin_connect_mcp.server import safe_call
from garmin_connect_mcp.service import GarminService


def test_timeout_terminates_worker(tmp_path):
    start = time.monotonic()
    with pytest.raises(RequestError, match="TIMEOUT"):
        execute_worker([sys.executable, "-c", "import time; time.sleep(5)"], "{}", timeout=.1)
    assert time.monotonic()-start < 3


def test_malformed_worker_response_is_sanitized():
    with pytest.raises(RequestError, match="WORKER_FAILED"):
        execute_worker([sys.executable, "-c", "print('synthetic-secret')"], "{}", timeout=5)


def test_cache_labels_and_prevents_repeated_reads(tmp_path):
    calls = []
    def runner(*args):
        calls.append(1)
        return {"activityId":1, "distance":1000}
    service = GarminService(TokenStore(tmp_path), runner)
    first, second = service.get_activity("1"), service.get_activity("1")
    assert not first["cached"] and second["cached"]
    assert first["fetched_at_utc"] == second["fetched_at_utc"]
    assert len(calls) == 1


def test_expired_cache_refetches_and_is_bounded(tmp_path):
    service = GarminService(TokenStore(tmp_path), lambda *args: {"activityId":1})
    service.get_activity("1")
    key = next(iter(service.cache))
    _, stamp, raw = service.cache[key]
    service.cache[key] = (-1000, stamp, raw)
    assert not service.get_activity("1")["cached"]
    for i in range(2, 135):
        service.get_activity(str(i))
    assert len(service.cache) == 128


def test_rate_limit_and_auth_are_never_retried(tmp_path):
    for code in ["RATE_LIMITED", "AUTH_REQUIRED"]:
        calls = []
        def runner(*args):
            calls.append(1)
            raise RequestError(code)
        with pytest.raises(RequestError):
            GarminService(TokenStore(tmp_path), runner).get_activity("1")
        assert len(calls) == 1


def test_network_retry_is_bounded(tmp_path):
    calls = []
    def runner(*args):
        calls.append(1)
        raise RequestError("NETWORK_ERROR")
    with pytest.raises(RequestError):
        GarminService(TokenStore(tmp_path), runner).get_activity("1")
    assert len(calls) == 2


def test_concurrent_reads_are_serialized(tmp_path):
    guard = threading.Lock()
    active = []
    def runner(*args):
        assert guard.acquire(blocking=False)
        active.append(1)
        time.sleep(.02)
        guard.release()
        return {"activityId":1}
    service = GarminService(TokenStore(tmp_path), runner)
    with ThreadPoolExecutor(4) as pool:
        list(pool.map(service.get_activity, ["1", "2", "3", "4"]))
    assert len(active) == 4


def test_exception_secrets_never_reach_tools():
    def fail():
        raise RuntimeError("password=synthetic-secret")
    assert "synthetic-secret" not in str(safe_call(fail))


@pytest.mark.parametrize("status,code", [(400,"INVALID_REQUEST"),(404,"NOT_FOUND"),(429,"RATE_LIMITED"),(503,"UPSTREAM_ERROR")])
def test_upstream_status_classification(status, code):
    assert error_code(Exception(f"API Error {status} - synthetic-secret")) == code


def test_local_logout_invalidates_cached_account_data(tmp_path):
    store = TokenStore(tmp_path)
    store.save('{"token":"synthetic"}')
    calls = []
    def runner(*args):
        calls.append(1)
        if not store.exists():
            raise RequestError("AUTH_REQUIRED")
        return {"activityId":1}
    service = GarminService(store, runner)
    service.get_activity("1")
    store.clear()
    with pytest.raises(RequestError, match="AUTH_REQUIRED"):
        service.get_activity("1")
    assert len(calls) == 2
