"""Account boundary; no credentials or Garmin calls in phase one."""

from typing import Protocol


class GarminAdapter(Protocol):
    def session_state(self) -> str: ...


class UnauthenticatedAdapter:
    def session_state(self) -> str:
        return "auth_required"

