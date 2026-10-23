"""Acquire the official Windows Codex registration helper only when needed."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import ssl
import time

from .setup_service import SetupError, bounded_request


def executable():
    existing = shutil.which('codex')
    if existing:
        return existing
    standard = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/OpenAI/Codex/bin/codex.exe'
    if standard.is_file():
        return str(standard)
    if os.name != 'nt':
        raise SetupError('Install Codex using your system installer, then select Connect Codex again.')
    return _download()


def _download():
    import httpx
    import truststore
    from .frozen_install import default_root
    try:
        with httpx.Client(verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT), timeout=30,
                follow_redirects=True, max_redirects=5, headers={'User-Agent': 'GarminConnectSetup'}) as client:
            code, body = bounded_request(client, 'GET', 'https://api.github.com/repos/openai/codex/releases/latest', 2 * 1024 * 1024)
            if code != 200:
                raise ValueError('Release lookup failed')
            metadata = json.loads(body)
            asset = next(item for item in metadata['assets'] if item['name'] == 'codex-x86_64-pc-windows-msvc.exe')
            digest = asset.get('digest', '')
            url = asset['browser_download_url']
            if (not re.fullmatch(r'sha256:[0-9a-f]{64}', digest)
                    or not url.startswith('https://github.com/openai/codex/releases/download/')
                    or not 0 < asset['size'] <= 600 * 1024 * 1024):
                raise ValueError('Unexpected release asset')
            root = default_root().resolve()
            folder = root / 'tools/codex' / digest[7:]
            if not folder.resolve().is_relative_to(root):
                raise ValueError('Helper directory escaped installation')
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / 'codex.exe'
            if target.is_file() and not target.is_symlink():
                with target.open('rb') as current:
                    if hashlib.file_digest(current, 'sha256').hexdigest() == digest[7:]:
                        return str(target)
            temporary = folder / 'codex.download'
            if temporary.is_symlink() or target.is_symlink():
                raise ValueError('Helper files cannot be links')
            sha = hashlib.sha256()
            total = 0
            deadline = time.monotonic() + 300
            try:
                with client.stream('GET', url) as response, temporary.open('wb') as output:
                    response.raise_for_status()
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        total += len(chunk)
                        if total > asset['size'] or time.monotonic() > deadline:
                            raise ValueError('Download exceeded bounds')
                        sha.update(chunk)
                        output.write(chunk)
                if total != asset['size'] or sha.hexdigest() != digest[7:]:
                    raise ValueError('Helper checksum mismatch')
                temporary.replace(target)
            finally:
                if temporary.exists():
                    temporary.unlink()
            return str(target)
    except Exception:
        raise SetupError('The official Codex helper could not be downloaded or verified. Check your internet connection and try again.') from None
