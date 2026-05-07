import logging
import os
import sys

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from config_store import ConfigStore
from schedule.repository import init_db, insert_sample_data
from slack.commands import register_commands
from scheduler import create_scheduler

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _require_env(name: str) -> str:
    val = os.getenv(name)
    if not val:
        logger.error("필수 환경 변수 누락: %s", name)
        sys.exit(1)
    return val


def _ensure_db_directory(db_path: str) -> None:
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)


def main() -> None:
    bot_token = _require_env("SLACK_BOT_TOKEN")
    signing_secret = _require_env("SLACK_SIGNING_SECRET")
    api_key = _require_env("OPENWEATHER_API_KEY")
    channel_id = _require_env("SLACK_CHANNEL_ID")
    notify_time = os.getenv("NOTIFY_TIME", "07:00")
    db_path = os.getenv("DB_PATH", "./data/bot.db")
    app_token = os.getenv("SLACK_APP_TOKEN", "")

    _ensure_db_directory(db_path)
    init_db(db_path)

    # 샘플 데이터가 없을 때만 삽입
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    if count == 0:
        insert_sample_data(db_path)

    app = App(token=bot_token, signing_secret=signing_secret)
    config_store = ConfigStore(db_path)

    register_commands(app, config_store, api_key, db_path)

    default_city = os.getenv("DEFAULT_CITY", "Seoul")
    scheduler = create_scheduler(app, channel_id, api_key, db_path, default_city, notify_time, config_store)
    scheduler.start()
    logger.info("스케줄러 시작 완료")

    if app_token:
        logger.info("Socket Mode로 시작")
        handler = SocketModeHandler(app, app_token)
        handler.start()
    else:
        port = int(os.getenv("PORT", 3000))
        logger.info("HTTP 모드로 시작 (포트: %d)", port)
        app.start(port=port)


if __name__ == "__main__":
    main()
