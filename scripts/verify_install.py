"""Offline installed-runtime check: real MCP handshake, tools and HTTP guard."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import tempfile

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(receipt):
    metadata = json.loads(receipt.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as temporary:
        environment = os.environ.copy()
        environment["GARMIN_MCP_DATA_DIR"] = temporary
        server = StdioServerParameters(command=metadata["python"],
            args=["-m", "garmin_connect_mcp.manage", "serve"], env=environment)
        async with stdio_client(server) as streams:
            async with ClientSession(*streams) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert len(tools.tools) == 35
                status = await session.call_tool("connection_status", {})
                value = json.loads(status.content[0].text)
                assert value["server_version"] == metadata["version"]
                assert value["session_state"] == "auth_required"
                contract = await session.call_tool("get_garmin_write_schema", {"operation": "schedule_workout"})
                assert not contract.isError
        if metadata["remote"]:
            import httpx
            from garmin_connect_mcp.remote import create_http_app
            previous = os.environ.get("GARMIN_MCP_DATA_DIR")
            os.environ["GARMIN_MCP_DATA_DIR"] = temporary
            try:
                app, _ = create_http_app("https://install-test.example", 8787)
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://install-test.example") as client:
                    response = await client.post("/mcp", json={})
                    assert response.status_code == 401
            finally:
                if previous is None:
                    os.environ.pop("GARMIN_MCP_DATA_DIR", None)
                else:
                    os.environ["GARMIN_MCP_DATA_DIR"] = previous
    print("PASS: installed MCP handshake, 35 tools, offline schema and optional HTTP authentication guard.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    asyncio.run(verify(parser.parse_args().receipt))
