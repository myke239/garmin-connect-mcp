"""Checksums describe final executables and ignore everything else."""
import hashlib
import importlib.util
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    "executable_checksums", Path(__file__).parents[1] / "scripts/executable_checksums.py")
checksums = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checksums)


def test_directory_hashes_each_executable_and_skips_other_files(tmp_path):
    bundle = tmp_path / "garmin-connect"
    bundle.mkdir()
    console = bundle / "garmin-connect.exe"
    desktop = bundle / "garmin-connect-desktop.exe"
    console.write_bytes(b"console")
    desktop.write_bytes(b"desktop")
    (bundle / "readme.txt").write_text("not an executable")
    (bundle / "_internal").mkdir()
    (bundle / "_internal" / "library.dll").write_bytes(b"library")
    output = tmp_path / "SHA256SUMS"
    notes = tmp_path / "notes.md"
    notes.write_text("# Release\n\nKeep this paragraph.\n")
    notes_output = tmp_path / "release-notes.md"

    text = checksums.write_checksums([bundle], output, notes, notes_output)

    expected = "".join(
        f"{hashlib.sha256(payload).hexdigest()}  {name}\n"
        for name, payload in (
            ("garmin-connect-desktop.exe", b"desktop"),
            ("garmin-connect.exe", b"console"),
        )
    )
    assert text == expected
    assert output.read_text(encoding="utf-8") == expected
    published = notes_output.read_text(encoding="utf-8")
    assert published.startswith("# Release\n\nKeep this paragraph.\n\n## SHA256 checksums\n")
    assert "```text\n" + expected + "```\n" in published


def test_setup_executable_is_included_by_name(tmp_path):
    installer = tmp_path / "garmin-connect-mcp-0.18.1-windows-x64-setup.exe"
    installer.write_bytes(b"setup")
    output = tmp_path / "out" / "SHA256SUMS"
    text = checksums.write_checksums([installer], output)
    assert text == f"{hashlib.sha256(b'setup').hexdigest()}  {installer.name}\n"


def test_rejects_empty_directory_foreign_file_duplicate_and_link(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(ValueError, match="No executables"):
        checksums.collect([empty], tmp_path / "SHA256SUMS")

    foreign = tmp_path / "notes.txt"
    foreign.write_text("no")
    with pytest.raises(ValueError, match="Not a built executable"):
        checksums.collect([foreign], tmp_path / "SHA256SUMS")

    first = tmp_path / "one"
    second = tmp_path / "two"
    first.mkdir()
    second.mkdir()
    (first / "garmin-connect").write_bytes(b"a")
    (second / "garmin-connect").write_bytes(b"b")
    with pytest.raises(ValueError, match="one file per name"):
        checksums.collect([first, second], tmp_path / "SHA256SUMS")

    link = tmp_path / "garmin-connect.exe"
    link.symlink_to(first / "garmin-connect")
    with pytest.raises(ValueError, match="Refusing to hash a link"):
        checksums.collect([link], tmp_path / "SHA256SUMS")

    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "garmin-connect").write_bytes(b"real")
    (nested / "library.so").symlink_to(nested / "garmin-connect")
    hashed = checksums.collect([nested], tmp_path / "SHA256SUMS")
    assert [path.name for path in hashed] == ["garmin-connect"]
    (nested / "garmin-connect-desktop").symlink_to(nested / "garmin-connect")
    with pytest.raises(ValueError, match="Refusing to hash a link"):
        checksums.collect([nested], tmp_path / "SHA256SUMS")
