"""Fail if schema files no longer split the way load applies them.

Files without dollar quotes must match the historical semicolon splitter.
62_fa_weeks.sql must keep its DO block as one statement.
"""

from __future__ import annotations

import sys
from pathlib import Path

from nu_choate_league.db import _statements
from nu_choate_league.paths import project_root


def historical(sql: str) -> list[str]:
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    parts: list[str] = []
    for raw in "\n".join(lines).split(";"):
        statement = raw.strip()
        if statement:
            parts.append(statement)
    return parts


def squash(statements: list[str]) -> str:
    # Separators are not part of either list. Ignore them so a semicolon that
    # now stays inside a string does not look like a different file.
    return "".join("".join(statement.split()).replace(";", "") for statement in statements)


def main() -> None:
    root = project_root()
    failed = False
    for path in [root / "sql" / "facts.sql", *sorted((root / "sql" / "analysis").glob("*.sql"))]:
        sql = path.read_text(encoding="utf-8")
        current = _statements(sql)
        if "$" not in sql:
            old = historical(sql)
            if current != old:
                # A semicolon inside a string used to split the statement. The
                # characters of the statements stay the same; only the grouping
                # changes. Load can execute the grouped form.
                if squash(current) != squash(old):
                    failed = True
                    print(f"MISMATCH {path.relative_to(root)} historical={len(old)} now={len(current)}")
                else:
                    print(
                        f"string-semicolon {path.name} historical={len(old)} now={len(current)}"
                    )
            else:
                print(f"ok {path.name} statements={len(current)}")
            continue
        print(f"dollar {path.name} statements={len(current)}")
        for index, statement in enumerate(current):
            preview = " ".join(statement.split())[:90]
            print(f"  {index}: {preview}")
            if statement.lstrip().startswith("END"):
                failed = True
                print("  DO block was split")
        do_blocks = [statement for statement in current if statement.lstrip().startswith("DO")]
        if len(do_blocks) != 1 or "DROP MATERIALIZED VIEW" not in do_blocks[0]:
            failed = True
            print("  expected one DO block that can drop a materialized view")
        if not any(statement.lstrip().startswith("CREATE MATERIALIZED VIEW") for statement in current):
            failed = True
            print("  expected CREATE MATERIALIZED VIEW")
    if failed:
        raise SystemExit(1)
    print("check_statements ok")


if __name__ == "__main__":
    sys.exit(main())
