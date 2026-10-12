"""Explicitly invoked live MCP check. Prints checks, not private activity data."""

import asyncio
import json
import sys
import os
import argparse
import tomllib
from pathlib import Path
from datetime import date, timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(codex_config=False):
    command, arguments = sys.executable, ["-m", "garmin_connect_mcp.cli", "serve"]
    if codex_config:
        config_path = Path(os.environ.get("CODEX_HOME", str(Path.home()/".codex"))) / "config.toml"
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        server = config["mcp_servers"]["garmin-connect"]
        command, arguments = server["command"], server["args"]
    parameters = StdioServerParameters(command=command, args=arguments)
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert len(tools.tools) == 7
            assert all(tool.annotations.readOnlyHint for tool in tools.tools)
            async def call(name, args):
                result = await client.call_tool(name, args)
                assert not result.isError
                body = json.loads(result.content[0].text)
                assert "error" not in body, body.get("error")
                return body
            end = date.today()
            args = {"start_date": (end-timedelta(days=89)).isoformat(), "end_date": end.isoformat(),
                    "activity_type": "running", "limit": 1}
            page = await call("list_activities", args)
            assert page["activities"], "No running activity in last 90 days"
            cached = await call("list_activities", args)
            assert cached["cached"]
            identity = {"activity_id": page["activities"][0]["activity_id"]}
            detail = await call("get_activity", identity)
            assert "distance_m" in detail["activity"]
            await call("get_activity_splits", identity)
            samples = await call("get_activity_samples", {**identity, "max_points":20})
            assert len(samples["samples"]) <= 20
            summary = await call("get_training_summary", {"start_date":(end-timedelta(days=6)).isoformat(),
                                                          "end_date":end.isoformat()})
            assert "coverage_complete" in summary
            print("Live MCP passed: 7 read-only tools; run/detail/splits/samples/summary; cache verified.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-config", action="store_true")
    options = parser.parse_args()
    asyncio.run(asyncio.wait_for(verify(options.codex_config), timeout=180))
