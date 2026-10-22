"""Write SHA256 checksums for final built executables, never account data."""
import argparse
import hashlib
from pathlib import Path

EXECUTABLE_NAMES = {
    "garmin-connect",
    "garmin-connect.exe",
    "garmin-connect-desktop",
    "garmin-connect-desktop.exe",
}


def is_executable(path):
    name = path.name
    if name in EXECUTABLE_NAMES:
        return True
    return name.startswith("garmin-connect-mcp-") and name.endswith("-setup.exe")


def collect(paths, output):
    found = []
    output_resolved = output.resolve()
    for raw in paths:
        if raw.is_symlink():
            raise ValueError(f"Refusing to hash a link: {raw}")
        path = raw.resolve()
        if path == output_resolved:
            raise ValueError("Checksum output cannot be an input")
        if path.is_dir():
            for child in sorted(path.rglob("*")):
                if not is_executable(child):
                    continue
                if child.is_symlink():
                    raise ValueError(f"Refusing to hash a link: {child}")
                if child.is_file() and child.resolve() != output_resolved:
                    found.append(child)
        elif path.is_file():
            if not is_executable(path):
                raise ValueError(f"Not a built executable: {raw}")
            found.append(path)
        else:
            raise ValueError(f"Missing build path: {raw}")
    unique = []
    seen = set()
    for path in sorted(found, key=lambda item: item.name):
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    names = [path.name for path in unique]
    if len(names) != len(set(names)):
        raise ValueError("Executable checksums need one file per name")
    if not unique:
        raise ValueError("No executables to hash")
    return unique


def checksums(files):
    lines = []
    for path in files:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append(f"{digest}  {path.name}")
    return "\n".join(lines) + "\n"


def with_release_notes(notes, sums):
    text = notes.read_text(encoding="utf-8").rstrip()
    return (
        text
        + "\n\n## SHA256 checksums\n\n"
        + "Compare the executable you downloaded or extracted with the matching line. "
        + "These are the final files from this build. Unsigned CI artifacts are not this list.\n\n"
        + "```text\n"
        + sums
        + "```\n"
    )


def write_checksums(paths, output, notes=None, notes_output=None):
    if (notes is None) != (notes_output is None):
        raise ValueError("Release notes source and output are both required")
    files = collect(paths, output)
    sums = checksums(files)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(sums, encoding="utf-8", newline="\n")
    if notes is not None:
        notes_output.parent.mkdir(parents=True, exist_ok=True)
        notes_output.write_text(with_release_notes(notes, sums), encoding="utf-8", newline="\n")
    return sums


def main(argv=None):
    parser = argparse.ArgumentParser(description="SHA256 checksums for built executables")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--release-notes", type=Path)
    parser.add_argument("--release-notes-output", type=Path)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        write_checksums(args.paths, args.output, args.release_notes, args.release_notes_output)
    except ValueError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
