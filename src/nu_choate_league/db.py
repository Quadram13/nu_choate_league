from __future__ import annotations

import os
import time
from collections.abc import Callable

import psycopg
from dotenv import load_dotenv

from .paths import project_root

FACTS_FILE = "sql/facts.sql"
ANALYSIS_DIR = "sql/analysis"

Progress = Callable[[str], None]


def load_env() -> None:
    env_file = project_root() / ".env"
    if env_file.is_file():
        load_dotenv(env_file)
    else:
        load_dotenv()


def database_url() -> str:
    load_env()
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("Missing DATABASE_URL. Set it in .env (see .env.example).")
    return url


def connect() -> psycopg.Connection:
    return psycopg.connect(database_url())


def schema_files() -> list:
    """Facts first, then analysis views in numeric-prefix (dependency) order."""
    root = project_root()
    files = [root / FACTS_FILE]
    files.extend(sorted((root / ANALYSIS_DIR).glob("*.sql")))
    return files


def apply_schema(
    conn: psycopg.Connection,
    *,
    refresh: bool = True,
    progress: Progress | None = None,
) -> None:
    for path in schema_files():
        started = time.perf_counter()
        sql = path.read_text(encoding="utf-8")
        for statement in _statements(sql):
            conn.execute(statement)
        if progress:
            progress(f"schema {path.name} ({time.perf_counter() - started:.1f}s)")
    if refresh:
        refresh_analysis(conn, progress=progress)


# Load applies schema before it truncates facts, then refreshes these
# snapshots. Later names read earlier ones. The fa chain reads plain views
# (and, when those are snapshots too, the fa snapshot before them).
# The players-index names read plain views, not each other, and not the fa
# chain. 60_players.sql and 97_volatility.sql drop them by CASCADE; the
# snapshot file recreates them before this refresh.
ANALYSIS_SNAPSHOTS = (
    "v_asset_value",
    "v_optimal_slots",
    "v_universe_outcomes",
    "v_waiver_claims",
    "v_all_league",
    "v_marks_weeks",
    "v_fa_weeks",
    "v_fa_season",
    "v_fa_career",
    "v_players_index_vol_season",
    "v_players_index_vol_career",
    "v_players_index_career",
    "v_players_index_season",
    "v_players_index_gap",
)


def refresh_analysis(conn: psycopg.Connection, progress: Progress | None = None) -> None:
    for name in ANALYSIS_SNAPSHOTS:
        started = time.perf_counter()
        if progress:
            progress(f"refresh {name}")
        conn.execute(f"REFRESH MATERIALIZED VIEW {name}")
        if progress:
            progress(f"refresh {name} ({time.perf_counter() - started:.1f}s)")


def _statements(sql: str) -> list[str]:
    """Split a schema file into statements execute() can run one at a time.

    Full-line ``--`` comments are dropped, same as the historical splitter.
    Semicolons inside quotes, dollar quotes, and line comments stay put, so
    a DO block that drops either a view or a materialized view is one statement.
    """
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    body = "\n".join(lines)
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    n = len(body)
    while i < n:
        ch = body[i]
        if ch == "-" and i + 1 < n and body[i + 1] == "-":
            newline = body.find("\n", i)
            if newline == -1:
                buf.append(body[i:])
                break
            buf.append(body[i:newline])
            i = newline
            continue
        if ch == "'":
            buf.append(ch)
            i += 1
            while i < n:
                buf.append(body[i])
                if body[i] == "'":
                    if i + 1 < n and body[i + 1] == "'":
                        buf.append(body[i + 1])
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            continue
        if ch == "$":
            j = i + 1
            while j < n and (body[j].isalnum() or body[j] == "_"):
                j += 1
            if j < n and body[j] == "$":
                tag = body[i : j + 1]
                end = body.find(tag, j + 1)
                if end == -1:
                    buf.append(body[i:])
                    break
                end += len(tag)
                buf.append(body[i:end])
                i = end
                continue
        if ch == ";":
            statement = "".join(buf).strip()
            if statement:
                parts.append(statement)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts
