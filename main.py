import logging
import os
import sys
import threading

import psycopg2
import uvicorn
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from api import create_api
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


def _count_courses() -> int:
    conn = psycopg2.connect(os.environ["DATABASE_URL"])
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM courses")
            return cur.fetchone()[0]
    finally:
        conn.close()


def main() -> None:
    bot_token = _require_env("SLACK_BOT_TOKEN")
    signing_secret = _require_env("SLACK_SIGNING_SECRET")
    api_key = _require_env("OPENWEATHER_API_KEY")
    channel_id = _require_env("SLACK_CHANNEL_ID")
    _require_env("DATABASE_URL")

    notify_time = os.getenv("NOTIFY_TIME", "07:00")
    db_path = ""  # PostgreSQL 사용으로 불필요 (하위 호환용)
    app_token = os.getenv("SLACK_APP_TOKEN", "")

    init_db(db_path)

    if _count_courses() == 0:
        insert_sample_data(db_path)

    app = App(token=bot_token, signing_secret=signing_secret)
    config_store = ConfigStore(db_path)

    register_commands(app, config_store, api_key, db_path)

    default_city = os.getenv("DEFAULT_CITY", "Seoul")
    scheduler = create_scheduler(app, channel_id, api_key, db_path, default_city, notify_time, config_store)
    scheduler.start()
    logger.info("스케줄러 시작 완료")

    # FastAPI (캘린더 ICS) 백그라운드 실행
    api_app = create_api()
    api_port = int(os.getenv("API_PORT", 3000))
    api_thread = threading.Thread(
        target=uvicorn.run,
        args=(api_app,),
        kwargs={"host": "0.0.0.0", "port": api_port, "log_level": "warning"},
        daemon=True,
    )
    api_thread.start()
    logger.info("캘린더 API 시작 완료 (포트: %d)", api_port)

    if app_token:
        logger.info("Socket Mode로 시작")
        handler = SocketModeHandler(app, app_token)
        handler.start()
    else:
        logger.info("HTTP 모드로 시작")
        app.start(port=int(os.getenv("PORT", 3001)))


if __name__ == "__main__":
    main()
