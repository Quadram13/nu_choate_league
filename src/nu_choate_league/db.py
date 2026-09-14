from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv

from .paths import project_root

FACTS_FILE = "sql/facts.sql"
ANALYSIS_DIR = "sql/analysis"


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


def apply_schema(conn: psycopg.Connection, *, refresh: bool = True) -> None:
    for path in schema_files():
        sql = path.read_text(encoding="utf-8")
        for statement in _statements(sql):
            conn.execute(statement)
    if refresh:
        refresh_analysis(conn)


def refresh_analysis(conn: psycopg.Connection) -> None:
    for name in (
        "v_asset_value",
        "v_optimal_slots",
        "v_universe_outcomes",
        "v_waiver_claims",
    ):
        conn.execute(f"REFRESH MATERIALIZED VIEW {name}")


def _statements(sql: str) -> list[str]:
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    parts: list[str] = []
    for raw in "\n".join(lines).split(";"):
        statement = raw.strip()
        if statement:
            parts.append(statement)
    return parts
