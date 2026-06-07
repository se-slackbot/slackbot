from __future__ import annotations
import json
import logging
from typing import Any

from bot.database import db, placeholder, resolve_db_path

logger = logging.getLogger(__name__)

CREATE_USER_CONFIG = """
CREATE TABLE IF NOT EXISTS user_config (
    slack_user_id TEXT PRIMARY KEY,
    city          TEXT NOT NULL DEFAULT 'Seoul',
    region        TEXT NOT NULL DEFAULT 'Seoul',
    notify_time   TEXT NOT NULL DEFAULT '07:00',
    timezone      TEXT NOT NULL DEFAULT 'Asia/Seoul',
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

DEFAULT_CONFIG = {
    "city": "Seoul",
    "region": "Seoul",
    "notify_time": "07:00",
    "timezone": "Asia/Seoul",
}


class ConfigStore:
    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = resolve_db_path(db_path)
        with db(self.db_path) as cur:
            cur.execute(CREATE_USER_CONFIG)

    def get(self, slack_user_id: str) -> dict:
        with db(self.db_path, dict_rows=True) as cur:
            cur.execute(
                f"SELECT * FROM user_config WHERE slack_user_id = {placeholder(self.db_path)}",
                (slack_user_id,),
            )
            row = cur.fetchone()
        if row is None:
            return {"slack_user_id": slack_user_id, **DEFAULT_CONFIG, "settings": {}}
        return _to_config(row)

    def list_all(self) -> list[dict]:
        with db(self.db_path, dict_rows=True) as cur:
            cur.execute("SELECT * FROM user_config ORDER BY slack_user_id")
            return [_to_config(row) for row in cur.fetchall()]

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
        new_city = city or region or current["city"]
        new_region = region or city or current["region"]
        new_time = notify_time or str(current["notify_time"])[:5]
        new_tz = timezone or current["timezone"]
        new_settings = {**current["settings"], **(settings or {})}

        ph = placeholder(self.db_path)
        with db(self.db_path) as cur:
            cur.execute(
                f"""
                INSERT INTO user_config
                    (slack_user_id, city, region, notify_time, timezone, settings_json)
                VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph})
                ON CONFLICT (slack_user_id) DO UPDATE SET
                    city          = excluded.city,
                    region        = excluded.region,
                    notify_time   = excluded.notify_time,
                    timezone      = excluded.timezone,
                    settings_json = excluded.settings_json,
                    updated_at    = CURRENT_TIMESTAMP
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
        logger.info("사용자 설정 저장: %s → city=%s, time=%s", slack_user_id, new_city, new_time)


def _to_config(row) -> dict:
    config = dict(row)
    try:
        settings = json.loads(config.pop("settings_json", "{}"))
    except (TypeError, json.JSONDecodeError):
        settings = {}
    config["settings"] = settings if isinstance(settings, dict) else {}
    return config
