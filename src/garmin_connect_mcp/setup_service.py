"""Local setup operations. Never exposed as MCP tools; no secrets in command lines."""
import asyncio
import hashlib
import json
import os
import re
from pathlib import Path
import socket
import subprocess
import sys
import time

from .auth import TokenStore, data_directory, new_client
from .endpoints import CANONICAL, LEGACY, connection_info
from .launching import command
from .remote import OwnerProvider, public_origin, valid_callback, READ_SCOPE, WRITE_SCOPE
from .runtime import session_lock


class SetupError(Exception):
    """A short, safe instruction that may be displayed by the local wizard."""


def bounded_request(client, method, url, limit, **kwargs):
    deadline = time.monotonic() + 30
    data = bytearray()
    with client.stream(method, url, **kwargs) as response:
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > limit or time.monotonic() > deadline:
                raise SetupError('The server response was too large or too slow. Check your HTTPS address.')
        return response.status_code, bytes(data)


def login(email, password, prompt_mfa, cancelled=lambda: False, factory=None):
    if not email.strip() or not password:
        raise SetupError('Enter your Garmin email and password.')
    client = None
    try:
        client = (factory or new_client)(email.strip(), password, prompt_mfa=prompt_mfa)
        client.login()
        client.get_activities(0, 1)
        if cancelled():
            raise SetupError('Sign-in cancelled. Your session was not saved.')
        store = TokenStore()
        with session_lock(store):
            if cancelled():
                raise SetupError('Sign-in cancelled. Your session was not saved.')
            store.save(client.client.dumps())
    except SetupError:
        raise
    except Exception:
        raise SetupError('Garmin could not sign you in. Check your email, password, verification code and internet connection, then try again.') from None
    finally:
        if client is not None:
            client.password = None
        password = None


def _fingerprint(pending):
    return hashlib.sha256(json.dumps([pending['client_id'], pending['params']], sort_keys=True).encode()).hexdigest()


def connection_request(origin, ticket, since=0):
    """Review the exact code copied from the owner's browser, never a guessed request."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{20,100}', ticket):
        raise SetupError('Paste the connection code shown in your browser.')
    found = []
    for endpoint in (CANONICAL, LEGACY):
        provider = OwnerProvider(origin, endpoint=endpoint)
        if not provider.store.exists():
            continue
        with provider.state() as state:
            for candidate, pending in state['pending'].items():
                if candidate != ticket:
                    continue
                params = pending['params']
                if pending['approved'] or pending['expires_at'] - 300 < since:
                    continue
                if (params.get('resource') != provider.resource or not valid_callback(params['redirect_uri'])
                        or READ_SCOPE not in params['scopes'] or not set(params['scopes']) <= {READ_SCOPE, WRITE_SCOPE}):
                    continue
                found.append({'ticket': ticket, 'endpoint': endpoint.storage_name,
                    'client_id': pending['client_id'], 'callback': params['redirect_uri'],
                    'scopes': params['scopes'], 'resource': provider.resource,
                    'fingerprint': _fingerprint(pending)})
    if len(found) != 1:
        raise SetupError('This code was not found or has expired. Restart the Garmin connection in ChatGPT and paste the new code.')
    return found[0]


def approve_connection(origin, review):
    endpoint = next((item for item in (CANONICAL, LEGACY) if item.storage_name == review['endpoint']), None)
    if endpoint is None:
        raise SetupError('Restart the connection request in ChatGPT.')
    provider = OwnerProvider(origin, endpoint=endpoint)
    with provider.state() as state:
        pending = state['pending'].get(review['ticket'])
        if not pending or pending['approved'] or _fingerprint(pending) != review['fingerprint']:
            raise SetupError('This request changed or expired. Restart the connection in ChatGPT.')
        pending['approved'] = True


class Backend:
    def __init__(self):
        self.runtime = command('manage')
        self.frozen = bool(getattr(sys, 'frozen', False))
        self.started_at = time.time()
        self.review = None
        self.origin = ''

    def run(self, *args, timeout=90):
        modules = {'verify': ('cli', ['verify']), 'background-start': ('background', ['start']),
            'background-install': ('background', ['install']), 'install-local': ('frozen_install', [])}
        module, arguments = modules.get(args[0], ('manage', list(args)))
        invocation = ([self.runtime[0], '--internal-module', module, *arguments] if self.frozen else
            [self.runtime[0], '-m', 'garmin_connect_mcp.' + module, *arguments])
        result = subprocess.run(invocation, capture_output=True, timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if result.returncode:
            messages = {'verify': 'Your Garmin session could not be verified. Sign in again.',
                'install-plugin': 'Codex could not be connected. Install the Codex CLI, reopen setup, and try again.',
                'background-start': 'The connection could not start. Check your ngrok token and internet connection.'}
            raise SetupError(messages.get(args[0], 'This step did not finish. Try again.'))
        return result.stdout.decode('utf-8', errors='replace')

    def install(self):
        from .manage import installation
        if installation():
            return
        import sys
        if not getattr(sys, 'frozen', False):
            raise SetupError('Open the downloaded Windows setup executable, or start setup from your installed application.')
        self.run('install-local')
        from .frozen_install import default_root
        receipt = json.loads((default_root() / 'installation.json').read_text(encoding='utf-8'))
        self.runtime = [receipt['launcher']]

    def session_saved(self):
        return TokenStore().exists()

    def verify(self):
        self.run('verify')

    def connect_codex(self):
        from .manage import installation, register_plugin
        from .setup_codex import executable
        metadata = installation()
        if not metadata and self.frozen:
            metadata = json.loads((Path(self.runtime[0]).parent / 'installation.json').read_text(encoding='utf-8'))
        if not metadata:
            raise SetupError('Run the Windows installer before connecting Codex.')
        try:
            register_plugin(executable(), metadata['marketplace'], quiet=True)
        except SetupError:
            raise
        except Exception:
            raise SetupError('Codex could not be connected. Reopen Codex, then try again.') from None
        self.verify_tools()

    def verify_tools(self):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        async def check():
            parameters = StdioServerParameters(command=self.runtime[0], args=[*self.runtime[1:], 'serve'],
                env={**os.environ, 'GARMIN_MCP_TOOL_PROFILE': 'all'})
            async with stdio_client(parameters) as streams:
                async with ClientSession(*streams) as client:
                    await client.initialize()
                    tools = await client.list_tools()
                    if len(tools.tools) != 58:
                        raise SetupError('The installed tools did not pass verification. Run setup again.')
        asyncio.run(asyncio.wait_for(check(), timeout=35))

    def existing_origin(self):
        store = TokenStore(data_directory() / 'remote-status')
        try:
            if not store.exists():
                return ''
            from urllib.parse import urlsplit
            parts = urlsplit(json.loads(store.load()).get('url', ''))
            return public_origin(parts.scheme + '://' + parts.netloc)
        except Exception:
            return ''

    def check_server(self, value):
        import ssl
        import httpx
        import truststore
        try:
            origin = public_origin(value.strip())
            info = connection_info(origin)
            with httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=15,
                    follow_redirects=False, headers={'ngrok-skip-browser-warning': 'true'}) as client:
                code, body = bounded_request(client, 'GET', info['resource_metadata_url'], 65536)
                resource = json.loads(body)
                guard, _ = bounded_request(client, 'POST', info['server_url'], 65536, json={})
                if (code != 200 or resource.get('resource') != info['server_url']
                        or resource.get('authorization_servers') != [info['issuer']]
                        or guard != 401):
                    raise ValueError('Unexpected remote service')
            self.origin = origin
            return info['server_url']
        except Exception:
            raise SetupError('The Garmin server is not ready at this address. Keep your shared gateway running and check the HTTPS hostname.') from None

    def start_tunnel(self, token):
        try:
            with socket.create_connection(('127.0.0.1', 8787), timeout=1):
                raise SetupError('Another connector is already running. Go Back and choose the existing HTTPS address.')
        except OSError:
            pass
        store = TokenStore(data_directory() / 'remote-tunnel')
        if token:
            if any(c.isspace() for c in token):
                raise SetupError('Paste the ngrok authtoken without spaces.')
            store.save(json.dumps({'authtoken': token}))
        elif not store.exists():
            raise SetupError('Paste your ngrok authtoken.')
        token = None
        self.run('background-start')
        for _ in range(60):
            origin = self.existing_origin()
            if origin:
                try:
                    url = self.check_server(origin)
                except SetupError:
                    continue
                if os.name == 'nt':
                    self.run('background-install')
                return url
            time.sleep(.5)
        raise SetupError('The tunnel is still starting. Wait a moment, then try again.')

    def find_request(self, ticket):
        self.review = connection_request(self.origin, ticket.strip(), self.started_at)
        return self.review

    def approve(self):
        if not self.review:
            raise SetupError('Check the request first.')
        approve_connection(self.origin, self.review)

    def verify_chatgpt(self):
        import ssl
        import httpx
        import truststore
        if not self.review:
            raise SetupError('Approve the connection request first.')
        endpoint = CANONICAL if self.review['endpoint'] == CANONICAL.storage_name else LEGACY
        provider = OwnerProvider(self.origin, endpoint=endpoint)
        with provider.state() as state:
            grants = [v for v in state['access'].values() if v['client_id'] == self.review['client_id']
                and v['expires_at'] > time.time() and v['resource'] == provider.resource and READ_SCOPE in v['scopes']]
        if not grants:
            raise SetupError('Return to ChatGPT, select Continue, and install the plugin. Then check again.')
        try:
            with httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=25,
                    follow_redirects=False, headers={'ngrok-skip-browser-warning': 'true',
                    'Authorization': 'Bearer ' + grants[0]['token'], 'Accept': 'application/json, text/event-stream'}) as client:
                code, body = bounded_request(client, 'POST', provider.resource, 4 * 1024 * 1024,
                    json={'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}})
                value = json.loads(body)
                if code != 200 or not value.get('result', {}).get('tools'):
                    raise ValueError('Tool discovery failed')
        except Exception:
            raise SetupError('ChatGPT authorization exists, but the server did not pass its tool check. Check the connection and try again.') from None
        self.verify_tools()
