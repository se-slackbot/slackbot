import logging
import os
import sys
import threading

import uvicorn
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from bot.api import create_api
from bot.config_store import ConfigStore
from bot.database import init_google_tokens_db, resolve_db_path
from bot.courses import count_courses, init_db, insert_sample_data
from bot.commands import register_commands
from bot.scheduler import create_scheduler, parse_hhmm

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


def main() -> None:
    bot_token = _require_env("SLACK_BOT_TOKEN")
    signing_secret = _require_env("SLACK_SIGNING_SECRET")
    api_key = _require_env("OPENWEATHER_API_KEY")
    channel_id = _require_env("SLACK_CHANNEL_ID")

    notify_time = os.getenv("NOTIFY_TIME", "07:00")
    if parse_hhmm(notify_time) is None:
        logger.error("NOTIFY_TIME 형식이 올바르지 않습니다: %s (예: 07:00)", notify_time)
        sys.exit(1)

    db_path = resolve_db_path()
    init_db(db_path)
    init_google_tokens_db(db_path)
    if count_courses(db_path) == 0:
        insert_sample_data(db_path)

    app = App(token=bot_token, signing_secret=signing_secret)
    config_store = ConfigStore(db_path)
    register_commands(app, config_store, api_key, db_path)

    scheduler = create_scheduler(
        app, channel_id, api_key, db_path, os.getenv("DEFAULT_CITY", "Seoul"), notify_time, config_store
    )
    scheduler.start()
    logger.info("스케줄러 시작 완료")

    # FastAPI (캘린더 ICS) 백그라운드 실행
    api_port = int(os.getenv("API_PORT", 3000))
    threading.Thread(
        target=uvicorn.run,
        args=(create_api(),),
        kwargs={"host": "0.0.0.0", "port": api_port, "log_level": "warning"},
        daemon=True,
    ).start()
    logger.info("캘린더 API 시작 완료 (포트: %d)", api_port)

    app_token = os.getenv("SLACK_APP_TOKEN", "")
    if app_token:
        logger.info("Socket Mode로 시작")
        SocketModeHandler(app, app_token).start()
    else:
        logger.info("HTTP 모드로 시작")
        app.start(port=int(os.getenv("PORT", 3001)))


if __name__ == "__main__":
    main()
