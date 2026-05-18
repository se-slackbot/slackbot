from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = "./data/bot.db"


def resolve_db_path(db_path: str | None = None) -> str | None:
    if db_path is not None:
        return db_path
    if os.getenv("DATABASE_URL"):
        return None
    return os.getenv("DB_PATH", DEFAULT_DB_PATH)


def ensure_sqlite_directory(db_path: str) -> None:
    directory = os.path.dirname(db_path)
    if directory:
        Path(directory).mkdir(parents=True, exist_ok=True)


def is_postgres(db_path: str | None = None) -> bool:
    return resolve_db_path(db_path) is None


@contextmanager
def connect(db_path: str | None = None, *, dict_rows: bool = False) -> Iterator:
    resolved = resolve_db_path(db_path)
    if resolved is None:
        import psycopg2

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
    else:
        ensure_sqlite_directory(resolved)
        conn = sqlite3.connect(resolved)
        if dict_rows:
            conn.row_factory = sqlite3.Row

    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def cursor(conn, *, dict_rows: bool = False):
    if conn.__class__.__module__.startswith("sqlite3"):
        cur = conn.cursor()
    elif dict_rows:
        from psycopg2.extras import RealDictCursor

        cur = conn.cursor(cursor_factory=RealDictCursor)
    else:
        cur = conn.cursor()

    try:
        yield cur
    finally:
        cur.close()


def placeholder(db_path: str | None = None) -> str:
    return "%s" if is_postgres(db_path) else "?"


def now_sql(db_path: str | None = None) -> str:
    return "NOW()" if is_postgres(db_path) else "CURRENT_TIMESTAMP"
