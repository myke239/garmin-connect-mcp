"""Bounded read execution: timeout kills the worker rather than orphaning a thread."""

import contextlib
import json
import subprocess
import os
import re
import time
from pathlib import Path

from .auth import TokenStore, restore_session, restrict

ALLOWED = {"get_activity", "get_activity_splits", "get_activity_details", "get_activity_exercise_sets", "connectapi"}
ALLOWED |= {"mcp_commit_write", "get_workouts", "get_workout_by_id"}
ALLOWED |= {"get_scheduled_workouts", "get_scheduled_workout_by_id", "get_devices", "get_activity_types",
            "get_body_composition", "get_hydration_data", "get_blood_pressure"}


class RequestError(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def error_code(error):
    if isinstance(error,RequestError): return error.code
    from garminconnect import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError
    if isinstance(error, GarminConnectTooManyRequestsError):
        return "RATE_LIMITED"
    if isinstance(error, GarminConnectAuthenticationError):
        return "AUTH_REQUIRED"
    # Parse status internally; never return the exception or URL to the client.
    status = re.search(r"(?:Error|HTTP|error)\s*[(:]?\s*(\d{3})", str(error))
    if status:
        value = int(status[1])
        if value >= 500:
            return "UPSTREAM_ERROR"
        return {401:"AUTH_REQUIRED",403:"ACCESS_DENIED",404:"NOT_FOUND",429:"RATE_LIMITED"}.get(value, "INVALID_REQUEST")
    return "NETWORK_ERROR"


@contextlib.contextmanager
def session_lock(store):
    store.directory.mkdir(parents=True, exist_ok=True)
    restrict(store.directory)
    lockpath = store.directory / "request.lock"
    if lockpath.is_symlink() or lockpath.is_junction():
        raise RequestError("SESSION_ERROR")
    with lockpath.open("a+b") as lock:
        restrict(lockpath)
        lock.seek(0)
        if not lock.read(1):
            lock.write(b"0")
            lock.flush()
        started = time.monotonic()
        while True:
            try:
                lock.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic()-started > 30:
                    raise RequestError("BUSY") from None
                time.sleep(.1)
        try:
            yield
        finally:
            lock.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def worker(connection, directory, method, args, kwargs):
    import sys
    diagnostic = os.environ.get("GARMIN_MCP_DIAGNOSTICS") == "1"
    def stage(value):
        if diagnostic:
            print("Garmin worker: " + value, file=sys.stderr, flush=True)
    try:
        stage("started")
        if method not in ALLOWED or (method == "connectapi" and args[0] not in {"/activitylist-service/activities/search/activities", "/workout-service/workout/types"}):
            raise RequestError("INVALID_REQUEST")
        store = TokenStore(Path(directory))
        if not store.exists():
            raise RequestError("AUTH_REQUIRED")
        with session_lock(store):
            stage("locked")
            client = restore_session(store)
            stage("restored")
            if method == "mcp_commit_write":
                from .writes import execute
                raw = execute(client, directory, *args, **kwargs)
            else:
                raw = getattr(client, method)(*args, **kwargs)
            stage("read complete")
            store.save(client.client.dumps())
            if len(json.dumps(raw)) > 2_000_000:
                raise RequestError("RESPONSE_TOO_LARGE")
            connection.send((True, raw))
    except RequestError as error:
        connection.send((False, error.code))
    except Exception as error:
        connection.send((False, error_code(error)))
    finally:
        connection.close()


def execute_worker(command, payload, timeout):
    try:
        completed = subprocess.run(command, input=payload, text=True, capture_output=True,
                                   timeout=timeout,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for the child before raising.
        raise RequestError("TIMEOUT") from None
    if completed.returncode != 0:
        raise RequestError("WORKER_FAILED")
    try:
        success, result = json.loads(completed.stdout)
    except (ValueError, TypeError):
        raise RequestError("WORKER_FAILED") from None
    if not success:
        raise RequestError(result)
    return result


def bounded_request(directory, method, args, kwargs, timeout=45):
    import sys
    payload = json.dumps({"directory": str(directory), "method": method, "args": args, "kwargs": kwargs})
    return execute_worker([sys.executable, "-m", "garmin_connect_mcp.worker"], payload, timeout)
