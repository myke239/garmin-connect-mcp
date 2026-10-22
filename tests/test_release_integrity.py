"""Regression: Linux bundles need bounded internal links, never external content."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("release_manifest", Path(__file__).parents[1] / "scripts/release_manifest.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def link(path, target):
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("Symlink creation requires platform privileges")


def test_relative_internal_link_is_recorded_without_dereferencing(tmp_path):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    (bundle / "library.so.1").write_bytes(b"test-library")
    link(bundle / "library.so", "library.so.1")
    result = module.manifest(bundle, allow_internal_links=True)
    assert {"path": "library.so", "type": "symlink", "target": "library.so.1"} in result["files"]
    assert next(item for item in result["files"] if item["path"] == "library.so.1")["bytes"] == 12
    with pytest.raises(ValueError):
        module.manifest(bundle)


@pytest.mark.parametrize("kind", ["escape", "absolute", "broken", "cycle"])
def test_unsafe_bundle_link_is_rejected(tmp_path, kind):
    bundle = tmp_path / "bundle"
    bundle.mkdir()
    outside = tmp_path / "outside"
    outside.write_bytes(b"outside")
    target = {"escape": "../outside", "absolute": str(outside), "broken": "missing", "cycle": "link"}[kind]
    link(bundle / "link", target)
    with pytest.raises(ValueError):
        module.manifest(bundle, allow_internal_links=True)
