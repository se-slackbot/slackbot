import logging
import os
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from weather.fetcher import fetch_weather
from schedule.repository import get_courses_for_date
from slack.message_builder import build_daily_message
from slack.client import post_daily_brief

logger = logging.getLogger(__name__)


def _run_daily_brief(app, channel_id: str, api_key: str, db_path: str, city: str) -> None:
    logger.info("데일리 브리프 스케줄 실행 시작")
    try:
        weather = fetch_weather(city, api_key)
    except Exception as e:
        logger.error("날씨 수집 실패, 스케줄 스킵: %s", e)
        _notify_error(app, channel_id, f"날씨 수집 실패: {e}")
        return

    try:
        courses = get_courses_for_date(db_path, date.today())
    except Exception as e:
        logger.error("시간표 수집 실패, 스케줄 스킵: %s", e)
        _notify_error(app, channel_id, f"시간표 수집 실패: {e}")
        return

    blocks = build_daily_message(weather, courses)

    try:
        post_daily_brief(app, channel_id, blocks)
    except Exception as e:
        logger.error("메시지 전송 최종 실패: %s", e)


def _notify_error(app, channel_id: str, message: str) -> None:
    try:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f":rotating_light: [오류] {message}",
        )
    except Exception:
        pass


def create_scheduler(app, channel_id: str, api_key: str, db_path: str, city: str, notify_time: str) -> BackgroundScheduler:
    hour, minute = notify_time.split(":")
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        _run_daily_brief,
        trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone="Asia/Seoul"),
        args=[app, channel_id, api_key, db_path, city],
        id="daily_brief",
        replace_existing=True,
        misfire_grace_time=300,
        max_instances=1,
    )
    logger.info("스케줄러 등록: 매일 %s:%s", hour, minute)
    return scheduler
