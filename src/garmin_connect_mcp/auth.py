"""Interactive authentication and encrypted-at-rest session storage."""

import json
import logging
import os
import tempfile
from pathlib import Path


def data_directory() -> Path:
    configured = os.environ.get("GARMIN_MCP_DATA_DIR")
    if configured:
        return Path(configured).expanduser().absolute()
    if os.name == "nt":
        legacy = Path("D:/developer/.garmin-connect-mcp")
        if legacy.is_dir():
            return legacy  # Preserve existing credentials without moving them.
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "garmin-connect-mcp"
    return Path.home() / ".local/share/garmin-connect-mcp"


def silence_library_logs() -> None:
    for name in ("garminconnect", "garminconnect.client"):
        logger = logging.getLogger(name)
        logger.handlers = [logging.NullHandler()]
        logger.propagate = False
        logger.setLevel(logging.CRITICAL + 1)


def restrict(path: Path) -> None:
    if path.is_symlink() or path.is_junction():
        raise ValueError("Session paths cannot be symlinks")
    if os.name != "nt":
        path.chmod(0o700 if path.is_dir() else 0o600)
        return
    import win32api
    import win32con
    import win32security

    token = win32security.OpenProcessToken(win32api.GetCurrentProcess(), win32con.TOKEN_QUERY)
    try:
        sid = win32security.GetTokenInformation(token, win32security.TokenUser)[0]
    finally:
        token.Close()
    acl = win32security.ACL()
    flags = win32con.OBJECT_INHERIT_ACE | win32con.CONTAINER_INHERIT_ACE if path.is_dir() else 0
    acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, flags, win32con.GENERIC_ALL, sid)
    acl.AddAccessAllowedAceEx(win32security.ACL_REVISION, flags, win32con.GENERIC_ALL,
                             win32security.CreateWellKnownSid(win32security.WinLocalSystemSid))
    win32security.SetNamedSecurityInfo(
        str(path), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None, None, acl, None,
    )


class TokenStore:
    def __init__(self, directory: Path | None = None):
        self.directory = directory or data_directory()
        self.path = self.directory / ("session.dpapi" if os.name == "nt" else "session.json")

    def exists(self) -> bool:
        return self.path.is_file()

    def save(self, tokens: str) -> None:
        json.loads(tokens)
        self.directory.mkdir(parents=True, exist_ok=True)
        restrict(self.directory)
        raw = tokens.encode("utf-8")
        if os.name == "nt":
            import win32crypt
            raw = win32crypt.CryptProtectData(raw, "Garmin MCP", None, None, None, 1)
        descriptor, temporary = tempfile.mkstemp(dir=self.directory, prefix="session-")
        temporary_path = Path(temporary)
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(raw)
                output.flush()
                os.fsync(output.fileno())
            restrict(temporary_path)
            if self.path.is_symlink() or self.path.is_junction():
                raise ValueError("Session paths cannot be symlinks")
            temporary_path.replace(self.path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def load(self) -> str:
        restrict(self.directory)
        restrict(self.path)
        raw = self.path.read_bytes()
        if os.name == "nt":
            import win32crypt
            raw = win32crypt.CryptUnprotectData(raw, None, None, None, 1)[1]
        tokens = raw.decode("utf-8")
        json.loads(tokens)
        return tokens

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)


def new_client(*args, **kwargs):
    import truststore
    truststore.inject_into_ssl()
    from garminconnect import Garmin
    silence_library_logs()
    # Prevent the upstream library from writing plaintext tokens through its
    # environment-variable fallback. Our store owns all persistence.
    if os.environ.get("GARMINTOKENS"):
        raise ValueError("Unset GARMINTOKENS before using Garmin MCP")
    return Garmin(*args, retry_attempts=0, **kwargs)


def restore_session(store: TokenStore, factory=new_client):
    client = factory()
    client.login(store.load())
    store.save(client.client.dumps())
    return client


def interactive_login(store: TokenStore) -> None:
    from getpass import getpass
    import sys
    if not sys.stdin.isatty():
        raise ValueError("Login requires an interactive terminal")
    email = input("Garmin email: ").strip()
    password = getpass("Garmin password: ")
    client = new_client(email, password, prompt_mfa=lambda: getpass("Garmin MFA code: "))
    try:
        client.login()
        # Verify a read operation rather than accepting an untested token.
        client.get_activities(0, 1)
        store.save(client.client.dumps())
    finally:
        client.password = None
        password = None

