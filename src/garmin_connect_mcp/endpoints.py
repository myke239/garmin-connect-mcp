"""Fixed public routes: canonical shared-host namespace and legacy migration."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    prefix: str
    mcp_path: str
    storage_name: str

    def route(self, suffix):
        return self.prefix + suffix

    @property
    def authorization_metadata(self):
        return "/.well-known/oauth-authorization-server" + self.prefix

    @property
    def resource_metadata(self):
        return "/.well-known/oauth-protected-resource" + self.mcp_path


CANONICAL = Endpoint("/mcp/garmin-connect", "/mcp/garmin-connect/", "garmin-connect")
LEGACY = Endpoint("", "/mcp", "")


def connection_info(origin):
    """Public addresses only. Does not authenticate, start services or inspect tokens."""
    from .remote import public_origin
    origin = public_origin(origin)
    return {"server_url": origin + CANONICAL.mcp_path,
            "issuer": origin + CANONICAL.prefix,
            "resource_metadata_url": origin + CANONICAL.resource_metadata,
            "authorization_metadata_url": origin + CANONICAL.authorization_metadata,
            "health_url": origin + CANONICAL.route("/health"),
            "scopes": ["garmin:read", "garmin:write"],
            "legacy_server_url": origin + LEGACY.mcp_path,
            "migration": "Existing legacy grants stay on the legacy resource. Create a new connection for the namespaced URL; do not reset existing grants."}
