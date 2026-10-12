"""Offline local documentation integrity and MCP inventory checks."""
import asyncio
from pathlib import Path
import re
import subprocess
import unicodedata
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
CORE = {"README.md", "AGENTS.md"}


def anchors(text):
    found = set()
    counts = {}
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        if in_fence:
            continue
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", line)
        if match:
            title = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", match.group(1))
            slug = unicodedata.normalize("NFC", title).lower()
            slug = re.sub(r"[^\w\- ]", "", slug).replace(" ", "-")
            count = counts.get(slug, 0)
            counts[slug] = count + 1
            found.add(slug + ("-" + str(count) if count else ""))
    return found


async def inventory():
    from garmin_connect_mcp.server import create_server
    return {tool.name for tool in await create_server(tool_profile="all").list_tools()}


def main():
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=ROOT, text=True
    ).splitlines()
    pages = [ROOT / name for name in set(names) if name.endswith(".md") and (ROOT / name).is_file()]
    pages += [ROOT / "CONTRIBUTING", ROOT / "CHANGELOG", ROOT / "NOTICE"]
    errors = []
    for path in pages:
        text = path.read_text(encoding="utf-8")
        if path.parent == ROOT and path.suffix == ".md" and path.name not in CORE:
            errors.append(f"Move task-specific root document: {path.name}")
        if sum(line.lstrip().startswith("```") for line in text.splitlines()) % 2:
            errors.append(f"Unbalanced code fences: {path.relative_to(ROOT)}")
        for target in re.findall(r"\[[^]\n]*\]\(([^)\n]+)\)", text):
            target = target.strip("<>")
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            file, _, fragment = target.partition("#")
            destination = (path.parent / unquote(file)).resolve() if file else path
            if not destination.exists():
                errors.append(f"Broken link: {path.relative_to(ROOT)} -> {target}")
            elif fragment and destination.suffix == ".md":
                if unquote(fragment) not in anchors(destination.read_text(encoding="utf-8")):
                    errors.append(f"Missing heading: {path.relative_to(ROOT)} -> {target}")
    reference = (ROOT / "docs/reference/tools.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"^## ([a-z][a-z0-9_]+)$", reference, re.M))
    actual = asyncio.run(inventory())
    if actual != documented:
        errors.append(f"Tool inventory mismatch: missing={sorted(actual-documented)}, extra={sorted(documented-actual)}")
    if errors:
        raise SystemExit("\n".join(errors))
    print(f"PASS: {len(pages)} documents, local links/headings, fences, root layout and {len(actual)} MCP tools.")


if __name__ == "__main__":
    main()
