import logging
from datetime import date, timedelta

from slack_bolt import App

from weather.fetcher import fetch_weather
from schedule.repository import get_courses_for_date, DAY_MAP
from slack.message_builder import (
    build_weather_message,
    build_schedule_message,
    build_help_message,
)
from config_store import ConfigStore

logger = logging.getLogger(__name__)


def register_commands(app: App, config_store: ConfigStore, api_key: str, db_path: str) -> None:

    @app.command("/날씨")
    def cmd_weather(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()

        config = config_store.get(user_id)
        city = text if text else config["city"]

        try:
            weather = fetch_weather(city, api_key)
            respond(blocks=build_weather_message(weather), response_type="ephemeral")
        except Exception as e:
            logger.error("/날씨 실패: %s", e)
            respond(text=f":warning: 날씨 정보를 가져올 수 없습니다: {e}", response_type="ephemeral")

    @app.command("/시간표")
    def cmd_schedule(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip().lower()

        target, label = _parse_date_arg(text)

        try:
            courses = get_courses_for_date(db_path, target, user_id)
            respond(blocks=build_schedule_message(courses, label), response_type="ephemeral")
        except Exception as e:
            logger.error("/시간표 실패: %s", e)
            respond(text=f":warning: 시간표를 불러올 수 없습니다: {e}", response_type="ephemeral")

    @app.command("/설정")
    def cmd_config(ack, respond, say, command):
        ack()
        user_id = command["user_id"]
        parts = command.get("text", "").strip().split()

        if len(parts) < 1:
            respond(text=":warning: 사용법: `/설정 [도시] [HH:MM]`", response_type="ephemeral")
            return

        config = config_store.get(user_id)
        city = parts[0] if len(parts) >= 1 else config["city"]
        notify_time = parts[1] if len(parts) >= 2 else config["notify_time"]

        if not _is_valid_time(notify_time):
            respond(text=":warning: 시각 형식이 올바르지 않습니다 (예: 07:00)", response_type="ephemeral")
            return

        config_store.set(user_id, city=city, notify_time=notify_time)
        respond(
            text=f":white_check_mark: 설정이 저장되었습니다.\n• 도시: *{city}*\n• 알림 시각: *{notify_time}*",
            response_type="ephemeral",
        )
        try:
            say(
                channel=user_id,
                text=f":bell: 알림 설정 변경 완료 — {city}, 매일 {notify_time}",
            )
        except Exception:
            pass

    @app.command("/도움말")
    def cmd_help(ack, respond):
        ack()
        respond(blocks=build_help_message(), response_type="ephemeral")


def _parse_date_arg(text: str) -> tuple[date, str]:
    today = date.today()
    if not text or text == "오늘":
        return today, "오늘"
    if text == "내일":
        return today + timedelta(days=1), "내일"
    try:
        return date.fromisoformat(text), text
    except ValueError:
        return today, "오늘"


def _is_valid_time(t: str) -> bool:
    parts = t.split(":")
    if len(parts) != 2:
        return False
    try:
        h, m = int(parts[0]), int(parts[1])
        return 0 <= h <= 23 and 0 <= m <= 59
    except ValueError:
        return False
