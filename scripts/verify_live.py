"""Explicitly invoked live MCP check. Prints checks, not private activity data."""

import asyncio
import json
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import date, timedelta

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def verify(codex_config=False, plugin_root=None):
    command, arguments = sys.executable, ["-m", "garmin_connect_mcp.cli", "serve"]
    if codex_config:
        resolved = subprocess.run(["codex", "mcp", "get", "garmin-connect", "--json"],
                                  check=True, capture_output=True, text=True, timeout=30)
        server = json.loads(resolved.stdout)["transport"]
        command, arguments = server["command"], server["args"]
    parameters = StdioServerParameters(command=command, args=arguments)
    if plugin_root:
        server = json.loads((Path(plugin_root)/".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["garmin-connect"]
        parameters = StdioServerParameters(command=server["command"], args=server["args"])
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            tools = await client.list_tools()
            assert len(tools.tools) == 26
            assert {tool.name for tool in tools.tools if not tool.annotations.readOnlyHint} == {"prepare_garmin_write", "commit_garmin_write"}
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
            print("Live MCP passed: 26 tools discovered; read operations and cache verified; no writes performed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--codex-config", action="store_true")
    parser.add_argument("--plugin-root", help="Verify the actual installed plugin's MCP configuration")
    options = parser.parse_args()
    asyncio.run(asyncio.wait_for(verify(options.codex_config, options.plugin_root), timeout=180))
