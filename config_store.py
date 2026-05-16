from __future__ import annotations
import logging
import json
import copy
import os
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

CREATE_USER_CONFIG = """
CREATE TABLE IF NOT EXISTS user_config (
    slack_user_id TEXT PRIMARY KEY,
    city          TEXT NOT NULL DEFAULT 'Seoul',
    region        TEXT NOT NULL DEFAULT 'Seoul',
    notify_time   TEXT NOT NULL DEFAULT '07:00',
    timezone      TEXT NOT NULL DEFAULT 'Asia/Seoul',
    settings_json TEXT NOT NULL DEFAULT '{}',
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
)
"""

DEFAULT_CONFIG = {
    "city": "Seoul",
    "region": "Seoul",
    "notify_time": "07:00",
    "timezone": "Asia/Seoul",
    "settings": {},
}


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


class ConfigStore:
    def __init__(self, db_path: str) -> None:
        conn = _get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(CREATE_USER_CONFIG)
        finally:
            conn.close()

    def get(self, slack_user_id: str) -> dict:
        conn = _get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM user_config WHERE slack_user_id = %s",
                    (slack_user_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()
        if row:
            config = dict(row)
            config["settings"] = _loads_settings(config.pop("settings_json", "{}"))
            return config
        return {"slack_user_id": slack_user_id, **copy.deepcopy(DEFAULT_CONFIG)}

    def list_all(self) -> list[dict]:
        conn = _get_conn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM user_config ORDER BY slack_user_id")
                rows = cur.fetchall()
        finally:
            conn.close()
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

        conn = _get_conn()
        try:
            with conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO user_config
                            (slack_user_id, city, region, notify_time, timezone, settings_json)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (slack_user_id) DO UPDATE SET
                            city          = EXCLUDED.city,
                            region        = EXCLUDED.region,
                            notify_time   = EXCLUDED.notify_time,
                            timezone      = EXCLUDED.timezone,
                            settings_json = EXCLUDED.settings_json,
                            updated_at    = NOW()
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
        finally:
            conn.close()
        logger.info("사용자 설정 저장: %s → city=%s, time=%s", slack_user_id, new_city, new_time)


def _loads_settings(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}
