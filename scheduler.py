from __future__ import annotations

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config_store import ConfigStore
from weather.fetcher import fetch_weather
from schedule.repository import get_courses_for_date
from slack.message_builder import build_daily_message
from slack.client import post_daily_brief

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "Asia/Seoul"
_sent_user_briefs: set[tuple[str, str, str]] = set()


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


def _run_user_daily_brief(app, user_config: dict, api_key: str, db_path: str) -> None:
    user_id = user_config["slack_user_id"]
    city = user_config.get("city") or "Seoul"
    timezone = _valid_timezone(user_config.get("timezone"))
    today = datetime.now(ZoneInfo(timezone)).date()

    logger.info("사용자 데일리 브리프 실행 시작: %s", user_id)
    try:
        weather = fetch_weather(city, api_key)
    except Exception as e:
        logger.error("사용자 날씨 수집 실패: %s user=%s", e, user_id)
        _notify_error(app, user_id, f"날씨 수집 실패: {e}")
        return

    try:
        courses = get_courses_for_date(db_path, today, user_id)
    except Exception as e:
        logger.error("사용자 시간표 수집 실패: %s user=%s", e, user_id)
        _notify_error(app, user_id, f"시간표 수집 실패: {e}")
        return

    blocks = build_daily_message(weather, courses, timezone=timezone)

    try:
        post_daily_brief(app, user_id, blocks)
    except Exception as e:
        logger.error("사용자 메시지 전송 최종 실패: %s user=%s", e, user_id)


def _run_due_user_briefs(app, config_store: ConfigStore, api_key: str, db_path: str) -> None:
    for config in config_store.list_all():
        if not _is_user_brief_due(config):
            continue
        key = _user_brief_key(config)
        if key in _sent_user_briefs:
            continue
        _sent_user_briefs.add(key)
        _run_user_daily_brief(app, config, api_key, db_path)


def _is_user_brief_due(config: dict) -> bool:
    notify_time = config.get("notify_time", "")
    timezone = _valid_timezone(config.get("timezone"))
    now = datetime.now(ZoneInfo(timezone))
    return notify_time == now.strftime("%H:%M")


def _user_brief_key(config: dict) -> tuple[str, str, str]:
    timezone = _valid_timezone(config.get("timezone"))
    now = datetime.now(ZoneInfo(timezone))
    return (config["slack_user_id"], now.strftime("%Y-%m-%d"), config.get("notify_time", ""))


def _valid_timezone(timezone: str | None) -> str:
    timezone = timezone or DEFAULT_TIMEZONE
    try:
        ZoneInfo(timezone)
        return timezone
    except ZoneInfoNotFoundError:
        logger.warning("올바르지 않은 타임존, 기본값 사용: %s", timezone)
        return DEFAULT_TIMEZONE


def _notify_error(app, channel_id: str, message: str) -> None:
    try:
        app.client.chat_postMessage(
            channel=channel_id,
            text=f":rotating_light: [오류] {message}",
        )
    except Exception:
        pass


def create_scheduler(
    app,
    channel_id: str,
    api_key: str,
    db_path: str,
    city: str,
    notify_time: str,
    config_store: ConfigStore | None = None,
) -> BackgroundScheduler:
    hour, minute = notify_time.split(":")
    scheduler = BackgroundScheduler(timezone=DEFAULT_TIMEZONE)
    scheduler.add_job(
        _run_daily_brief,
        trigger=CronTrigger(hour=int(hour), minute=int(minute), timezone=DEFAULT_TIMEZONE),
        args=[app, channel_id, api_key, db_path, city],
        id="daily_brief",
        replace_existing=True,
        misfire_grace_time=300,
        max_instances=1,
    )
    logger.info("스케줄러 등록: 매일 %s:%s", hour, minute)
    if config_store is not None:
        scheduler.add_job(
            _run_due_user_briefs,
            trigger=CronTrigger(second=0, timezone=DEFAULT_TIMEZONE),
            args=[app, config_store, api_key, db_path],
            id="user_daily_briefs",
            replace_existing=True,
            misfire_grace_time=30,
            max_instances=1,
        )
        logger.info("사용자별 데일리 브리프 스케줄러 등록 완료")
    return scheduler
