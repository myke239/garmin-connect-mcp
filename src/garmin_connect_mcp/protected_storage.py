"""Fail-closed optional Secret Service encryption for Linux private stores."""
import hashlib
import json
import os
from pathlib import Path

MARKER = '.protected-store.json'


def configuration(directory: Path) -> Path | None:
    current=Path(directory).absolute()
    for root in (current,*current.parents):
        marker=root/MARKER
        if marker.is_file():
            if marker.is_symlink(): raise ValueError('Protected-storage marker cannot be a symlink')
            value=json.loads(marker.read_text(encoding='utf-8'))
            if value!={'backend':'secret-service','version':1}: raise ValueError('Unsupported protected storage configuration')
            return root
    return None


def backend():
    import keyring
    selected=keyring.get_keyring()
    # Never accept plaintext/third-party/chained/null fallback backends.
    if type(selected).__module__!='keyring.backends.SecretService':
        raise RuntimeError('An unlocked Linux Secret Service keyring is required; plaintext fallback refused')
    return selected


def cipher(root,create=False):
    from cryptography.fernet import Fernet
    selected=backend()
    identity=hashlib.sha256(str(Path(root).absolute()).encode()).hexdigest()
    key=selected.get_password('garmin-connect-mcp',identity)
    if key is None and create:
        key=Fernet.generate_key().decode()
        selected.set_password('garmin-connect-mcp',identity,key)
        if selected.get_password('garmin-connect-mcp',identity)!=key:
            raise RuntimeError('Protected keyring did not preserve its encryption key')
    if key is None: raise RuntimeError('Protected-storage key is unavailable; no plaintext fallback')
    return Fernet(key.encode())


def encode(directory,raw):
    root=configuration(directory)
    return b'GCMCP1:'+cipher(root).encrypt(raw) if root else raw


def decode(directory,raw):
    root=configuration(directory)
    if raw.startswith(b'GCMCP1:'):
        if root is None: raise RuntimeError('Protected-storage configuration is unavailable')
        return cipher(root).decrypt(raw[7:])
    # Plaintext records retained during interrupted migration may only be read
    # while root is marked; subsequent save encrypts them. Migration is explicit.
    if root is not None: cipher(root)  # Keyring must remain available even during interrupted migration.
    return raw


def migrate(root):
    if os.name=='nt': raise ValueError('Windows already uses DPAPI; no keyring migration needed')
    from .auth import restrict,TokenStore
    from .runtime import session_lock
    root=Path(root).absolute()
    root.mkdir(parents=True,exist_ok=True);restrict(root)
    # Excludes runtime/dependencies and arbitrary JSON. Only TokenStore files.
    records=list(root.rglob('session.json'))
    if len(records)>2000: raise ValueError('Too many private stores for one migration')
    for record in records:
        if record.is_symlink() or any(v.is_symlink() for v in record.parents if v!=root.parent):
            raise ValueError('Migration refuses symlinked private stores')
        json.loads(record.read_bytes().decode()) if configuration(root) is None else TokenStore(record.parent).load()
    cipher(root,create=True)  # Verify keyring before changing any file.
    marker=root/MARKER
    if marker.is_symlink(): raise ValueError('Marker cannot be a symlink')
    marker.write_text(json.dumps({'backend':'secret-service','version':1}),encoding='utf-8');restrict(marker)
    completed=0
    for record in records:
        store=TokenStore(record.parent)
        with session_lock(store):
            value=store.load();store.save(value)
            assert store.load()==value
        completed+=1
    return {'encrypted_stores':completed,'backend':'secret-service','plaintext_fallback':False}


def main():
    import argparse
    from .auth import data_directory
    parser=argparse.ArgumentParser(description='Optional Linux Secret Service migration; stop connector/services first')
    parser.add_argument('command',choices=['status','migrate'])
    args=parser.parse_args()
    if args.command=='migrate': print(json.dumps(migrate(data_directory())))
    else: print(json.dumps({'protected':configuration(data_directory()) is not None,'backend':'secret-service' if configuration(data_directory()) else 'owner-only'}))


if __name__=='__main__': main()
