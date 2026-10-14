"""Versioned installer registration preserves private state and newer pointers."""
import json
from pathlib import Path
import sys
import pytest
from garmin_connect_mcp import __version__
from garmin_connect_mcp import frozen_install


def bundle(tmp_path,monkeypatch):
    root=tmp_path/'application'
    source=root/'releases'/(__version__+'-installer');source.mkdir(parents=True)
    executable=source/'garmin-connect.exe';executable.write_bytes(b'synthetic')
    resources=tmp_path/'resources'
    plugin=resources/'plugins/garmin-connect';plugin.mkdir(parents=True)
    (plugin/'.mcp.json').write_text(json.dumps({'mcpServers':{'garmin-connect':{'command':'placeholder'}}}))
    index=resources/'marketplace-index';index.mkdir();(index/'marketplace.json').write_text('{}')
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'executable',str(executable))
    monkeypatch.setattr(sys,'_MEIPASS',str(resources),raising=False)
    monkeypatch.setattr(frozen_install,'default_root',lambda:root)
    monkeypatch.setattr('subprocess.run',lambda *args,**kwargs:None)
    return root,source


def test_registration_and_uninstall_preserve_newer_release_and_data(tmp_path,monkeypatch):
    root,source=bundle(tmp_path,monkeypatch)
    private=tmp_path/'private';private.mkdir();(private/'session.json').write_text('synthetic private state')
    frozen_install.register_bundle()
    receipt=root/'installation.json';value=json.loads(receipt.read_text())
    assert value['launcher']==str(source/'garmin-connect.exe')
    assert json.loads((source/'marketplace/plugins/garmin-connect/.mcp.json').read_text())['mcpServers']['garmin-connect']['args']==['serve']
    newer={**value,'launcher':str(root/'releases/newer/garmin-connect.exe')};receipt.write_text(json.dumps(newer))
    frozen_install.register_bundle(remove=True)
    assert json.loads(receipt.read_text())==newer
    receipt.write_text(json.dumps(value));frozen_install.register_bundle(remove=True)
    assert not receipt.exists() and (private/'session.json').read_text()=='synthetic private state'


def test_registration_refuses_unowned_location(tmp_path,monkeypatch):
    root,source=bundle(tmp_path,monkeypatch)
    monkeypatch.setattr(sys,'executable',str(tmp_path/'unrelated/garmin-connect.exe'))
    with pytest.raises(ValueError,match='standard versioned'):frozen_install.register_bundle()
    assert not (root/'installation.json').exists()
