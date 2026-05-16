import logging
import shlex
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from slack_bolt import App

from weather.fetcher import fetch_weather
from schedule.repository import add_course, delete_course, get_courses_for_date, update_course
from slack.message_builder import (
    build_weather_message,
    build_schedule_message,
    build_help_message,
)
from config_store import ConfigStore

logger = logging.getLogger(__name__)

WEATHER_COMMANDS = ("/날씨", "/날씨1", "/weather")
SCHEDULE_COMMANDS = ("/시간표", "/시간표1", "/schedule")
CONFIG_COMMANDS = ("/설정", "/config")
HELP_COMMANDS = ("/도움말", "/bot-help")


def register_commands(app: App, config_store: ConfigStore, api_key: str, db_path: str) -> None:

    def cmd_weather(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        logger.info("슬래시 커맨드 수신: %s user=%s", command.get("command"), user_id)

        config = config_store.get(user_id)
        city = text if text else config["city"]

        try:
            weather = fetch_weather(city, api_key)
            respond(blocks=build_weather_message(weather), response_type="ephemeral")
        except Exception as e:
            logger.error("/날씨 실패: %s", e)
            respond(text=f":warning: 날씨 정보를 가져올 수 없습니다: {e}", response_type="ephemeral")

    def cmd_schedule(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        logger.info("슬래시 커맨드 수신: %s user=%s text=%s", command.get("command"), user_id, text)

        if text.startswith("추가"):
            try:
                course = _parse_add_course_arg(text)
                course_id = add_course(db_path, user_id, **course)
                respond(
                    text=(
                        ":white_check_mark: 시간표에 추가했습니다.\n"
                        f"• ID: *{course_id}*\n"
                        f"• 과목: *{course['course_name']}*\n"
                        f"• 시간: *{course['day_of_week']} {course['start_time']}~{course['end_time']}*"
                    ),
                    response_type="ephemeral",
                )
            except ValueError as e:
                respond(text=f":warning: {e}", response_type="ephemeral")
            except Exception as e:
                logger.error("/시간표 추가 실패: %s", e)
                respond(text=f":warning: 시간표를 추가할 수 없습니다: {e}", response_type="ephemeral")
            return
        if text.startswith("수정"):
            try:
                course_id, fields = _parse_update_course_arg(text)
                updated = update_course(db_path, user_id, course_id, **fields)
                if not updated:
                    respond(
                        text=f":warning: 수정할 수 있는 개인 일정 ID `{course_id}`를 찾지 못했습니다.",
                        response_type="ephemeral",
                    )
                    return
                respond(
                    text=(
                        ":white_check_mark: 시간표를 수정했습니다.\n"
                        f"• ID: *{course_id}*\n"
                        f"• 변경: {', '.join(f'*{key}*' for key in fields)}"
                    ),
                    response_type="ephemeral",
                )
            except ValueError as e:
                respond(text=f":warning: {e}", response_type="ephemeral")
            except Exception as e:
                logger.error("/시간표 수정 실패: %s", e)
                respond(text=f":warning: 시간표를 수정할 수 없습니다: {e}", response_type="ephemeral")
            return
        if text.startswith("삭제"):
            try:
                course_id = _parse_delete_course_arg(text)
                deleted = delete_course(db_path, user_id, course_id)
                if not deleted:
                    respond(
                        text=f":warning: 삭제할 수 있는 개인 일정 ID `{course_id}`를 찾지 못했습니다.",
                        response_type="ephemeral",
                    )
                    return
                respond(
                    text=f":white_check_mark: 시간표에서 ID *{course_id}* 일정을 삭제했습니다.",
                    response_type="ephemeral",
                )
            except ValueError as e:
                respond(text=f":warning: {e}", response_type="ephemeral")
            except Exception as e:
                logger.error("/시간표 삭제 실패: %s", e)
                respond(text=f":warning: 시간표를 삭제할 수 없습니다: {e}", response_type="ephemeral")
            return

        target, label = _parse_date_arg(text.lower())

        try:
            courses = get_courses_for_date(db_path, target, user_id)
            respond(blocks=build_schedule_message(courses, label), response_type="ephemeral")
        except Exception as e:
            logger.error("/시간표 실패: %s", e)
            respond(text=f":warning: 시간표를 불러올 수 없습니다: {e}", response_type="ephemeral")

    def cmd_config(ack, respond, say, command):
        ack()
        user_id = command["user_id"]
        parts = command.get("text", "").strip().split()
        logger.info("슬래시 커맨드 수신: %s user=%s", command.get("command"), user_id)

        config = config_store.get(user_id)
        if len(parts) < 1:
            respond(
                text=(
                    ":gear: 현재 설정\n"
                    f"• 도시: *{config['city']}*\n"
                    f"• 알림 시각: *{config['notify_time']}*\n"
                    f"• 타임존: *{config['timezone']}*\n\n"
                    "변경하려면 `/config Seoul 07:00 Asia/Seoul` 또는 `/설정 Seoul 07:00 Asia/Seoul` 형식으로 입력하세요."
                ),
                response_type="ephemeral",
            )
            return

        city = parts[0] if len(parts) >= 1 else config["city"]
        notify_time = parts[1] if len(parts) >= 2 else config["notify_time"]
        timezone = parts[2] if len(parts) >= 3 else config["timezone"]

        if not _is_valid_time(notify_time):
            respond(text=":warning: 시각 형식이 올바르지 않습니다 (예: 07:00)", response_type="ephemeral")
            return
        if not _is_valid_timezone(timezone):
            respond(text=":warning: 타임존 형식이 올바르지 않습니다 (예: Asia/Seoul)", response_type="ephemeral")
            return

        config_store.set(user_id, city=city, notify_time=notify_time, timezone=timezone)
        respond(
            text=(
                ":white_check_mark: 설정이 저장되었습니다.\n"
                f"• 도시: *{city}*\n"
                f"• 알림 시각: *{notify_time}*\n"
                f"• 타임존: *{timezone}*"
            ),
            response_type="ephemeral",
        )
        try:
            say(
                channel=user_id,
                text=f":bell: 알림 설정 변경 완료 — {city}, 매일 {notify_time} ({timezone})",
            )
        except Exception:
            pass

    def cmd_help(ack, respond):
        ack()
        logger.info("슬래시 커맨드 수신: 도움말")
        respond(blocks=build_help_message(), response_type="ephemeral")

    _register_aliases(app, WEATHER_COMMANDS, cmd_weather)
    _register_aliases(app, SCHEDULE_COMMANDS, cmd_schedule)
    _register_aliases(app, CONFIG_COMMANDS, cmd_config)
    _register_aliases(app, HELP_COMMANDS, cmd_help)


def _register_aliases(app: App, command_names: tuple[str, ...], handler) -> None:
    for command_name in command_names:
        app.command(command_name)(handler)


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


def _is_valid_timezone(timezone: str) -> bool:
    try:
        ZoneInfo(timezone)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def _parse_add_course_arg(text: str) -> dict:
    try:
        parts = shlex.split(text)
    except ValueError:
        raise ValueError("입력 형식이 올바르지 않습니다. 공백이 있는 값은 따옴표로 감싸주세요.")

    if len(parts) < 5 or parts[0] != "추가":
        raise ValueError(
            "사용법: `/시간표 추가 <요일> <시작 HH:MM> <종료 HH:MM> <과목명> [장소] [교수] [메모]`"
        )

    day_of_week = _normalize_day(parts[1])
    start_time = parts[2]
    end_time = parts[3]
    course_name = parts[4]

    if not _is_valid_time(start_time) or not _is_valid_time(end_time):
        raise ValueError("시각 형식이 올바르지 않습니다 (예: 09:00 10:30)")
    if start_time >= end_time:
        raise ValueError("종료 시각은 시작 시각보다 늦어야 합니다.")

    return {
        "day_of_week": day_of_week,
        "start_time": start_time,
        "end_time": end_time,
        "course_name": course_name,
        "room": parts[5] if len(parts) >= 6 else None,
        "professor": parts[6] if len(parts) >= 7 else None,
        "memo": " ".join(parts[7:]) if len(parts) >= 8 else None,
    }


def _parse_update_course_arg(text: str) -> tuple[int, dict]:
    try:
        parts = shlex.split(text)
    except ValueError:
        raise ValueError("입력 형식이 올바르지 않습니다. 공백이 있는 값은 따옴표로 감싸주세요.")

    if len(parts) < 3 or parts[0] != "수정":
        raise ValueError(
            "사용법: `/시간표 수정 <ID> <field=value>...` "
            "(예: `/시간표 수정 12 room=공학관301호 start=10:00 end=11:30`)"
        )

    try:
        course_id = int(parts[1])
    except ValueError:
        raise ValueError("일정 ID는 숫자로 입력해주세요.")

    fields = {}
    for assignment in parts[2:]:
        if "=" not in assignment:
            raise ValueError("수정 항목은 `field=value` 형식으로 입력해주세요.")
        raw_key, value = assignment.split("=", 1)
        key = _normalize_update_field(raw_key)
        if key == "day_of_week":
            value = _normalize_day(value)
        fields[key] = value

    _validate_course_update_fields(fields)
    return course_id, fields


def _parse_delete_course_arg(text: str) -> int:
    try:
        parts = shlex.split(text)
    except ValueError:
        raise ValueError("입력 형식이 올바르지 않습니다.")

    if len(parts) != 2 or parts[0] != "삭제":
        raise ValueError("사용법: `/시간표 삭제 <ID>`")
    try:
        return int(parts[1])
    except ValueError:
        raise ValueError("일정 ID는 숫자로 입력해주세요.")


def _normalize_update_field(value: str) -> str:
    aliases = {
        "name": "course_name",
        "course": "course_name",
        "course_name": "course_name",
        "과목": "course_name",
        "과목명": "course_name",
        "day": "day_of_week",
        "day_of_week": "day_of_week",
        "요일": "day_of_week",
        "start": "start_time",
        "start_time": "start_time",
        "시작": "start_time",
        "end": "end_time",
        "end_time": "end_time",
        "종료": "end_time",
        "room": "room",
        "장소": "room",
        "professor": "professor",
        "교수": "professor",
        "memo": "memo",
        "메모": "memo",
    }
    try:
        return aliases[value.strip().lower()]
    except KeyError:
        raise ValueError("수정 가능한 항목: name, day, start, end, room, professor, memo")


def _validate_course_update_fields(fields: dict) -> None:
    start = fields.get("start_time")
    end = fields.get("end_time")
    if start is not None and not _is_valid_time(start):
        raise ValueError("시작 시각 형식이 올바르지 않습니다 (예: 09:00)")
    if end is not None and not _is_valid_time(end):
        raise ValueError("종료 시각 형식이 올바르지 않습니다 (예: 10:30)")
    if start is not None and end is not None and start >= end:
        raise ValueError("종료 시각은 시작 시각보다 늦어야 합니다.")
    if "course_name" in fields and not fields["course_name"]:
        raise ValueError("과목명은 비워둘 수 없습니다.")


def _normalize_day(value: str) -> str:
    day = value.strip().lower()
    day_aliases = {
        "mon": "Mon",
        "monday": "Mon",
        "월": "Mon",
        "월요일": "Mon",
        "tue": "Tue",
        "tuesday": "Tue",
        "화": "Tue",
        "화요일": "Tue",
        "wed": "Wed",
        "wednesday": "Wed",
        "수": "Wed",
        "수요일": "Wed",
        "thu": "Thu",
        "thursday": "Thu",
        "목": "Thu",
        "목요일": "Thu",
        "fri": "Fri",
        "friday": "Fri",
        "금": "Fri",
        "금요일": "Fri",
        "sat": "Sat",
        "saturday": "Sat",
        "토": "Sat",
        "토요일": "Sat",
        "sun": "Sun",
        "sunday": "Sun",
        "일": "Sun",
        "일요일": "Sun",
    }
    try:
        return day_aliases[day]
    except KeyError:
        raise ValueError("요일은 월~일 또는 Mon~Sun 형식으로 입력해주세요.")
