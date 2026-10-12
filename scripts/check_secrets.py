"""High-confidence secret/private-artifact gate over Git-tracked files only."""
import re,subprocess
from pathlib import Path

PATTERNS=[re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    re.compile(rb'gh[pousr]_[A-Za-z0-9]{36,}'),re.compile(rb'github_pat_[A-Za-z0-9_]{70,}'),
    re.compile(rb'AKIA[0-9A-Z]{16}'),re.compile(rb'eyJ[A-Za-z0-9_-]{80,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}')]
FORBIDDEN={'session.dpapi','session.json','.env','installation.json'}

def main():
    result=subprocess.run(['git','ls-files','-z'],check=True,capture_output=True)
    failures=[]
    for name in result.stdout.decode().split('\0'):
        if not name:continue
        path=Path(name)
        if path.name in FORBIDDEN or any(part in {'private','.venv','.venv313','work'} for part in path.parts):
            failures.append(name);continue
        content=path.read_bytes()
        if any(pattern.search(content) for pattern in PATTERNS):failures.append(name)
    if failures:
        print('Secret/private artifact check failed in '+', '.join(failures));raise SystemExit(1)
    print('PASS: tracked private-artifact and high-confidence secret checks (does not guarantee absence of every secret)')

if __name__=='__main__':main()
