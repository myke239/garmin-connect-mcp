"""Package a verified portable build; no signing or installer claims."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tarfile
import zipfile
from release_manifest import manifest


def package(bundle, output, platform):
    version = Path("VERSION").read_text(encoding="utf-8").strip()
    if platform not in {"windows", "linux"}:
        raise ValueError("Unsupported release platform")
    output.mkdir(parents=True, exist_ok=True)
    integrity = manifest(bundle, allow_internal_links=platform == "linux")
    if integrity["source_dirty"]:
        raise ValueError("Release requires a clean checkout")
    integrity.update(version=version, platform=platform + "-x64", signing="unsigned")
    stem = f"garmin-connect-mcp-{version}-{platform}-x64"
    (output / (stem + "-integrity.json")).write_text(json.dumps(integrity, indent=2) + "\n", encoding="utf-8")
    if platform == "windows":
        archive = output / (stem + ".zip")
        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
            for path in sorted(bundle.rglob("*")):
                if path.is_file():
                    target.write(path, "garmin-connect/" + path.relative_to(bundle).as_posix())
    else:
        for name in ("garmin-connect", "garmin-connect-desktop"):
            os.chmod(bundle / name, 0o755)
        archive = output / (stem + ".tar.gz")
        with tarfile.open(archive, "w:gz", dereference=False) as target:
            target.add(bundle, arcname="garmin-connect")
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    print(f"{checksum}  {archive.name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--platform", choices=["windows", "linux"], required=True)
    args = parser.parse_args()
    package(args.bundle, args.output, args.platform)
