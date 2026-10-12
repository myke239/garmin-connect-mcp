"""Exercise the actual subprocess transport without Garmin credentials."""

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_stdio_lifecycle():
    async def exercise():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "garmin_connect_mcp.server"],
        )
        async with stdio_client(parameters) as (read, write):
            async with ClientSession(read, write) as client:
                await client.initialize()
                listing = await client.list_tools()
                assert len(listing.tools) == 35
                assert {tool.name for tool in listing.tools if not tool.annotations.readOnlyHint} == {"prepare_garmin_write", "commit_garmin_write", "commit_garmin_workout_creation", "commit_garmin_workout_update", "commit_garmin_workout_schedule", "commit_garmin_training_calendar"}
                assert listing.tools[0].annotations.readOnlyHint is True
                response = await client.call_tool("connection_status", {})
                assert not response.isError
                data = json.loads(response.content[0].text)
                assert data["session_state"] in ("auth_required", "saved_session")
                assert data["garmin_verified"] is False
                unknown = await client.call_tool("delete_activity", {})
                assert unknown.isError

    asyncio.run(asyncio.wait_for(exercise(), timeout=20))

