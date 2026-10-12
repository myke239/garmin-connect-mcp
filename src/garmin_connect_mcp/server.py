"""MCP stdio entry point. stdout belongs exclusively to the protocol."""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from . import __version__
from .adapter import GarminAdapter, UnauthenticatedAdapter


def create_server(adapter: GarminAdapter | None = None) -> FastMCP:
    backend = adapter if adapter is not None else UnauthenticatedAdapter()
    server = FastMCP("garmin-connect-mcp")

    @server.tool(annotations=ToolAnnotations(
        readOnlyHint=True, destructiveHint=False, openWorldHint=False,
    ))
    def connection_status() -> dict[str, str | bool]:
        """Check local server state. This does not contact Garmin or verify a token."""
        return {
            "server_version": __version__,
            "session_state": backend.session_state(),
            "garmin_verified": False,
            "phase": "foundation",
        }

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()

