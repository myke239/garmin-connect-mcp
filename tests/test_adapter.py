import asyncio

from garmin_connect_mcp.server import create_server


def test_injected_adapter_does_not_claim_live_verification():
    class FakeAdapter:
        def session_state(self):
            return "cached_session"

    result = asyncio.run(create_server(FakeAdapter()).call_tool("connection_status", {}))
    # FastMCP returns content plus structured data for typed dictionary tools.
    structured = result[1] if isinstance(result, tuple) else result
    assert structured["session_state"] == "cached_session"
    assert structured["garmin_verified"] is False

