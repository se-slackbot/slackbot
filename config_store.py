from __future__ import annotations
import sqlite3
import logging
import json
import copy
from typing import Any

logger = logging.getLogger(__name__)

CREATE_USER_CONFIG = """
CREATE TABLE IF NOT EXISTS user_config (
    slack_user_id TEXT PRIMARY KEY,
    city          TEXT NOT NULL DEFAULT 'Seoul',
    region        TEXT NOT NULL DEFAULT 'Seoul',
    notify_time   TEXT NOT NULL DEFAULT '07:00',
    timezone      TEXT NOT NULL DEFAULT 'Asia/Seoul',
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

DEFAULT_CONFIG = {
    "city": "Seoul",
    "region": "Seoul",
    "notify_time": "07:00",
    "timezone": "Asia/Seoul",
    "settings": {},
}


def _ensure_columns(conn: sqlite3.Connection) -> None:
    columns = {
        row[1] for row in conn.execute("PRAGMA table_info(user_config)").fetchall()
    }
    migrations = [
        ("region", "ALTER TABLE user_config ADD COLUMN region TEXT NOT NULL DEFAULT 'Seoul'"),
        ("settings_json", "ALTER TABLE user_config ADD COLUMN settings_json TEXT NOT NULL DEFAULT '{}'"),
        ("created_at", "ALTER TABLE user_config ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "ALTER TABLE user_config ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"),
    ]
    for column, statement in migrations:
        if column not in columns:
            conn.execute(statement)
    conn.execute("UPDATE user_config SET region = city WHERE region = 'Seoul' AND city != 'Seoul'")
    conn.execute("UPDATE user_config SET created_at = CURRENT_TIMESTAMP WHERE created_at = ''")
    conn.execute("UPDATE user_config SET updated_at = CURRENT_TIMESTAMP WHERE updated_at = ''")


class ConfigStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with sqlite3.connect(db_path) as conn:
            conn.execute(CREATE_USER_CONFIG)
            _ensure_columns(conn)
            conn.commit()

    def get(self, slack_user_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM user_config WHERE slack_user_id = ?", (slack_user_id,)
            ).fetchone()
        if row:
            config = dict(row)
            config["settings"] = _loads_settings(config.pop("settings_json", "{}"))
            return config
        return {"slack_user_id": slack_user_id, **copy.deepcopy(DEFAULT_CONFIG)}

    def list_all(self) -> list[dict]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM user_config ORDER BY slack_user_id"
            ).fetchall()

        configs = []
        for row in rows:
            config = dict(row)
            config["settings"] = _loads_settings(config.pop("settings_json", "{}"))
            configs.append(config)
        return configs

    def set(
        self,
        slack_user_id: str,
        city: str | None = None,
        notify_time: str | None = None,
        timezone: str | None = None,
        region: str | None = None,
        settings: dict[str, Any] | None = None,
    ) -> None:
        current = self.get(slack_user_id)
        new_region = region or city or current["region"]
        new_city = city or region or current["city"]
        new_time = notify_time or current["notify_time"]
        new_tz = timezone or current["timezone"]
        new_settings = current["settings"].copy()
        if settings is not None:
            new_settings.update(settings)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_config (slack_user_id, city, region, notify_time, timezone, settings_json)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(slack_user_id) DO UPDATE SET
                    city = excluded.city,
                    region = excluded.region,
                    notify_time = excluded.notify_time,
                    timezone = excluded.timezone,
                    settings_json = excluded.settings_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    slack_user_id,
                    new_city,
                    new_region,
                    new_time,
                    new_tz,
                    json.dumps(new_settings, ensure_ascii=False, sort_keys=True),
                ),
            )
            conn.commit()
        logger.info("사용자 설정 저장: %s → city=%s, time=%s", slack_user_id, new_city, new_time)


def _loads_settings(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
