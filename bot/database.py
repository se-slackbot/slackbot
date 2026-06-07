from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

DEFAULT_DB_PATH = "./data/bot.db"

CREATE_GOOGLE_TOKENS = """
CREATE TABLE IF NOT EXISTS google_tokens (
    slack_user_id TEXT PRIMARY KEY,
    token_json    TEXT NOT NULL,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


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


def placeholder(db_path: str | None = None) -> str:
    return "%s" if is_postgres(db_path) else "?"


@contextmanager
def db(db_path: str | None = None, *, dict_rows: bool = False) -> Iterator:
    """커서를 열어 주고, 예외 없이 끝나면 커밋한다. (예외 시 close 로 롤백)"""
    resolved = resolve_db_path(db_path)
    if resolved is None:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        conn = psycopg2.connect(os.environ["DATABASE_URL"])
        cur = conn.cursor(cursor_factory=RealDictCursor) if dict_rows else conn.cursor()
    else:
        ensure_sqlite_directory(resolved)
        conn = sqlite3.connect(resolved)
        if dict_rows:
            conn.row_factory = sqlite3.Row
        cur = conn.cursor()

    try:
        yield cur
        conn.commit()
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Google 토큰 DB 저장 (파일시스템이 휘발되는 배포 환경 대응)
# ---------------------------------------------------------------------------


def init_google_tokens_db(db_path: str | None = None) -> None:
    with db(db_path) as cur:
        cur.execute(CREATE_GOOGLE_TOKENS)


def get_google_token(slack_user_id: str, db_path: str | None = None) -> str | None:
    with db(db_path) as cur:
        cur.execute(
            f"SELECT token_json FROM google_tokens WHERE slack_user_id = {placeholder(db_path)}",
            (slack_user_id,),
        )
        row = cur.fetchone()
    return row[0] if row else None


def save_google_token(slack_user_id: str, token_json: str, db_path: str | None = None) -> None:
    ph = placeholder(db_path)
    with db(db_path) as cur:
        cur.execute(
            f"""
            INSERT INTO google_tokens (slack_user_id, token_json)
            VALUES ({ph}, {ph})
            ON CONFLICT (slack_user_id) DO UPDATE SET
                token_json = excluded.token_json,
                updated_at = CURRENT_TIMESTAMP
            """,
            (slack_user_id, token_json),
        )
