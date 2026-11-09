"""Fail if a write statement lives outside the load pipeline.

Same-name snapshots stay correct only if fact rows change in load.py,
which refreshes the snapshots after the insert.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from nu_choate_league.paths import project_root

# Statement-level writes. ON DELETE CASCADE is a foreign key, not a write.
WRITE = re.compile(r"\b(INSERT\s+INTO|UPDATE\s+\w+|COPY\s+\w+|TRUNCATE\b|DELETE\s+FROM)\b")
ALLOWED = {
    Path("src/nu_choate_league/load.py"),
}


def main() -> None:
    root = project_root()
    hits: list[tuple[Path, int, str, str]] = []
    for directory in (root / "src", root / "scripts", root / "sql"):
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.suffix.lower() not in {".py", ".ps1", ".sql"}:
                continue
            if ".venv" in path.parts or path.name == "check_writes.py":
                continue
            text = path.read_text(encoding="utf-8")
            for number, line in enumerate(text.splitlines(), start=1):
                match = WRITE.search(line)
                if match:
                    hits.append((path.relative_to(root), number, match.group(1), line.strip()))
    outside = [hit for hit in hits if hit[0] not in ALLOWED]
    print(f"write_hits={len(hits)} outside_load={len(outside)}")
    for path, number, kind, line in hits:
        flag = "" if path in ALLOWED else " OUTSIDE"
        print(f"{kind}{flag} {path}:{number}: {line[:140]}")
    if outside:
        raise SystemExit(1)
    print("check_writes ok")


if __name__ == "__main__":
    sys.exit(main())
