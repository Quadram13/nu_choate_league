from __future__ import annotations

import os

import psycopg
from dotenv import load_dotenv

from .paths import project_root

SCHEMA_FILES = ("sql/facts.sql", "sql/analysis.sql")


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


def apply_schema(conn: psycopg.Connection) -> None:
    root = project_root()
    for name in SCHEMA_FILES:
        sql = (root / name).read_text(encoding="utf-8")
        for statement in _statements(sql):
            conn.execute(statement)


def _statements(sql: str) -> list[str]:
    lines = [line for line in sql.splitlines() if not line.strip().startswith("--")]
    parts: list[str] = []
    for raw in "\n".join(lines).split(";"):
        statement = raw.strip()
        if statement:
            parts.append(statement)
    return parts
