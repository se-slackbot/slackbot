import sqlite3
import logging

logger = logging.getLogger(__name__)

CREATE_USER_CONFIG = """
CREATE TABLE IF NOT EXISTS user_config (
    slack_user_id TEXT PRIMARY KEY,
    city          TEXT NOT NULL DEFAULT 'Seoul',
    notify_time   TEXT NOT NULL DEFAULT '07:00',
    timezone      TEXT NOT NULL DEFAULT 'Asia/Seoul'
)
"""

DEFAULT_CONFIG = {"city": "Seoul", "notify_time": "07:00", "timezone": "Asia/Seoul"}


class ConfigStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        with sqlite3.connect(db_path) as conn:
            conn.execute(CREATE_USER_CONFIG)
            conn.commit()

    def get(self, slack_user_id: str) -> dict:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM user_config WHERE slack_user_id = ?", (slack_user_id,)
            ).fetchone()
        if row:
            return dict(row)
        return {"slack_user_id": slack_user_id, **DEFAULT_CONFIG}

    def set(self, slack_user_id: str, city: str | None = None, notify_time: str | None = None, timezone: str | None = None) -> None:
        current = self.get(slack_user_id)
        new_city = city or current["city"]
        new_time = notify_time or current["notify_time"]
        new_tz = timezone or current["timezone"]

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO user_config (slack_user_id, city, notify_time, timezone)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(slack_user_id) DO UPDATE SET
                    city = excluded.city,
                    notify_time = excluded.notify_time,
                    timezone = excluded.timezone
                """,
                (slack_user_id, new_city, new_time, new_tz),
            )
            conn.commit()
        logger.info("사용자 설정 저장: %s → city=%s, time=%s", slack_user_id, new_city, new_time)
