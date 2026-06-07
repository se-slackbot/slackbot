import logging
import shlex
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from slack_bolt import App

from bot.weather import fetch_weather
from bot.courses import (
    add_course,
    delete_course,
    get_all_courses_for_user,
    get_courses_for_date,
    update_course,
)
from bot.message_builder import (
    build_course_list_message,
    build_weather_message,
    build_schedule_message,
    build_help_message,
)
from bot.config_store import ConfigStore
from bot.scheduler import build_brief, is_valid_timezone, parse_hhmm, valid_timezone

logger = logging.getLogger(__name__)

WEATHER_COMMANDS = ("/날씨", "/날씨1", "/weather")
SCHEDULE_COMMANDS = ("/시간표", "/시간표1", "/schedule")
CONFIG_COMMANDS = ("/설정", "/설정1", "/config")
HELP_COMMANDS = ("/도움말", "/bot-help")
BRIEF_COMMANDS = ("/브리핑", "/브리핑1", "/brief")

SCHEDULE_ACTIONS = ("추가", "수정", "삭제", "목록")

UPDATE_FIELD_ALIASES = {
    alias: field
    for field, aliases in {
        "course_name": ("name", "course", "과목", "과목명"),
        "day_of_week": ("day", "요일"),
        "start_time": ("start", "시작"),
        "end_time": ("end", "종료"),
        "room": ("장소",),
        "professor": ("교수",),
        "memo": ("메모",),
    }.items()
    for alias in (field, *aliases)
}

DAY_ALIASES = {
    alias: name[:3]
    for name, korean in zip(
        ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"),
        "월화수목금토일",
    )
    for alias in (name[:3].lower(), name.lower(), korean, f"{korean}요일")
}


def _reply(respond, **kwargs) -> None:
    """슬래시 커맨드 응답은 항상 본인에게만 보인다."""
    respond(response_type="ephemeral", **kwargs)


@contextmanager
def _warn_on_error(respond, message: str):
    """실패하면 경고로 응답한다. 입력 오류(ValueError)는 그 메시지를 그대로 보여준다."""
    try:
        yield
    except ValueError as e:
        _reply(respond, text=f":warning: {e}")
    except Exception as e:
        logger.error("%s: %s", message, e)
        _reply(respond, text=f":warning: {message}: {e}")


def register_commands(app: App, config_store: ConfigStore, api_key: str, db_path: str | None = None) -> None:

    def cmd_weather(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        logger.info("슬래시 커맨드 수신: %s user=%s", command.get("command"), user_id)

        with _warn_on_error(respond, "날씨 정보를 가져올 수 없습니다"):
            city = text or config_store.get(user_id)["city"]
            _reply(respond, blocks=build_weather_message(fetch_weather(city, api_key)))

    def cmd_schedule(ack, respond, command):
        ack()
        user_id = command["user_id"]
        text = command.get("text", "").strip()
        logger.info("슬래시 커맨드 수신: %s user=%s text=%s", command.get("command"), user_id, text)

        action = next((a for a in SCHEDULE_ACTIONS if text.startswith(a)), None)
        if action == "목록":
            with _warn_on_error(respond, "시간표를 불러올 수 없습니다"):
                _reply(respond, blocks=build_course_list_message(get_all_courses_for_user(user_id, db_path)))
            return
        if action:
            with _warn_on_error(respond, f"시간표를 {action}할 수 없습니다"):
                _reply(respond, text=_apply_schedule_action(action, text, db_path, user_id))
            return

        with _warn_on_error(respond, "시간표를 불러올 수 없습니다"):
            today = _today(config_store.get(user_id).get("timezone"))
            target, label = _parse_date_arg(text.lower(), today)
            courses = get_courses_for_date(db_path, target, user_id)
            _reply(respond, blocks=build_schedule_message(courses, label))

    def cmd_config(ack, respond, say, command):
        ack()
        user_id = command["user_id"]
        parts = command.get("text", "").strip().split()
        logger.info("슬래시 커맨드 수신: %s user=%s parts=%s", command.get("command"), user_id, parts)

        config = config_store.get(user_id)
        city = parts[0] if parts else config["city"]
        notify_time = parts[1] if len(parts) >= 2 else str(config["notify_time"])[:5]
        timezone = parts[2] if len(parts) >= 3 else config["timezone"]
        summary = f"• 도시: *{city}*\n• 알림 시각: *{notify_time}*\n• 타임존: *{timezone}*"

        if not parts:
            _reply(
                respond,
                text=(
                    f":gear: 현재 설정\n{summary}\n\n"
                    "변경하려면 `/config Seoul 07:00 Asia/Seoul` 또는 `/설정 Seoul 07:00 Asia/Seoul` 형식으로 입력하세요."
                ),
            )
            return

        with _warn_on_error(respond, "설정 저장 실패"):
            if parse_hhmm(notify_time) is None:
                raise ValueError("시각 형식이 올바르지 않습니다 (예: 07:00)")
            if not is_valid_timezone(timezone):
                raise ValueError("타임존 형식이 올바르지 않습니다 (예: Asia/Seoul)")

            config_store.set(user_id, city=city, notify_time=notify_time, timezone=timezone)
            _reply(respond, text=f":white_check_mark: 설정이 저장되었습니다.\n{summary}")
            try:
                say(channel=user_id, text=f":bell: 알림 설정 변경 완료 — {city}, 매일 {notify_time} ({timezone})")
            except Exception:
                pass

    def cmd_help(ack, respond):
        ack()
        logger.info("슬래시 커맨드 수신: 도움말")
        _reply(respond, blocks=build_help_message())

    def cmd_brief(ack, respond, command):
        ack()
        user_id = command["user_id"]
        logger.info("슬래시 커맨드 수신: 브리핑 user=%s", user_id)

        config = config_store.get(user_id)
        with _warn_on_error(respond, "브리핑을 가져올 수 없습니다"):
            blocks = build_brief(
                api_key,
                db_path,
                config.get("city") or "Seoul",
                valid_timezone(config.get("timezone")),
                user_id,
            )
            _reply(respond, blocks=blocks)

    handlers = (
        (WEATHER_COMMANDS, cmd_weather),
        (SCHEDULE_COMMANDS, cmd_schedule),
        (CONFIG_COMMANDS, cmd_config),
        (HELP_COMMANDS, cmd_help),
        (BRIEF_COMMANDS, cmd_brief),
    )
    for command_names, handler in handlers:
        for command_name in command_names:
            app.command(command_name)(handler)


def _apply_schedule_action(action: str, text: str, db_path: str | None, user_id: str) -> str:
    """추가/수정/삭제를 실행하고 성공 메시지를 돌려준다. 실패는 ValueError."""
    if action == "추가":
        course = _parse_add_course_arg(text)
        course_id = add_course(db_path, user_id, **course)
        return (
            ":white_check_mark: 시간표에 추가했습니다.\n"
            f"• ID: *{course_id}*\n"
            f"• 과목: *{course['course_name']}*\n"
            f"• 시간: *{course['day_of_week']} {course['start_time']}~{course['end_time']}*"
        )
    if action == "수정":
        course_id, fields = _parse_update_course_arg(text)
        if not update_course(db_path, user_id, course_id, **fields):
            raise ValueError(f"수정할 수 있는 개인 일정 ID `{course_id}`를 찾지 못했습니다.")
        return (
            ":white_check_mark: 시간표를 수정했습니다.\n"
            f"• ID: *{course_id}*\n"
            f"• 변경: {', '.join(f'*{key}*' for key in fields)}"
        )
    course_id = _parse_delete_course_arg(text)
    if not delete_course(db_path, user_id, course_id):
        raise ValueError(f"삭제할 수 있는 개인 일정 ID `{course_id}`를 찾지 못했습니다.")
    return f":white_check_mark: 시간표에서 ID *{course_id}* 일정을 삭제했습니다."


def _today(timezone: str | None) -> date:
    return datetime.now(ZoneInfo(valid_timezone(timezone))).date()


def _parse_date_arg(text: str, today: date | None = None) -> tuple[date, str]:
    today = today or date.today()
    if text == "내일":
        return today + timedelta(days=1), "내일"
    try:
        return date.fromisoformat(text), text
    except ValueError:
        return today, "오늘"


def _split_args(text: str) -> list[str]:
    try:
        return shlex.split(text)
    except ValueError:
        raise ValueError("입력 형식이 올바르지 않습니다. 공백이 있는 값은 따옴표로 감싸주세요.")


def _validate_times(start: str | None, end: str | None) -> None:
    for label, value in (("시작", start), ("종료", end)):
        if value is not None and parse_hhmm(value) is None:
            raise ValueError(f"{label} 시각 형식이 올바르지 않습니다 (예: 09:00)")
    if start is not None and end is not None and start >= end:
        raise ValueError("종료 시각은 시작 시각보다 늦어야 합니다.")


def _parse_add_course_arg(text: str) -> dict:
    parts = _split_args(text)
    if len(parts) < 5 or parts[0] != "추가":
        raise ValueError(
            "사용법: `/시간표 추가 <요일> <시작 HH:MM> <종료 HH:MM> <과목명> [장소] [교수] [메모]`"
        )

    _, day, start_time, end_time, course_name, *rest = parts
    day_of_week = _normalize_day(day)
    _validate_times(start_time, end_time)

    return {
        "day_of_week": day_of_week,
        "start_time": start_time,
        "end_time": end_time,
        "course_name": course_name,
        "room": rest[0] if rest else None,
        "professor": rest[1] if len(rest) >= 2 else None,
        "memo": " ".join(rest[2:]) or None,
    }


def _parse_update_course_arg(text: str) -> tuple[int, dict]:
    parts = _split_args(text)
    if len(parts) < 3 or parts[0] != "수정":
        raise ValueError(
            "사용법: `/시간표 수정 <ID> <field=value>...` "
            "(예: `/시간표 수정 12 room=공학관301호 start=10:00 end=11:30`)"
        )

    course_id = _parse_course_id(parts[1])
    fields = {}
    for assignment in parts[2:]:
        if "=" not in assignment:
            raise ValueError("수정 항목은 `field=value` 형식으로 입력해주세요.")
        raw_key, value = assignment.split("=", 1)
        key = _normalize_update_field(raw_key)
        fields[key] = _normalize_day(value) if key == "day_of_week" else value

    _validate_times(fields.get("start_time"), fields.get("end_time"))
    if "course_name" in fields and not fields["course_name"]:
        raise ValueError("과목명은 비워둘 수 없습니다.")
    return course_id, fields


def _parse_delete_course_arg(text: str) -> int:
    parts = _split_args(text)
    if len(parts) != 2 or parts[0] != "삭제":
        raise ValueError("사용법: `/시간표 삭제 <ID>`")
    return _parse_course_id(parts[1])


def _parse_course_id(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        raise ValueError("일정 ID는 숫자로 입력해주세요.")


def _normalize_update_field(value: str) -> str:
    try:
        return UPDATE_FIELD_ALIASES[value.strip().lower()]
    except KeyError:
        raise ValueError("수정 가능한 항목: name, day, start, end, room, professor, memo")


def _normalize_day(value: str) -> str:
    try:
        return DAY_ALIASES[value.strip().lower()]
    except KeyError:
        raise ValueError("요일은 월~일 또는 Mon~Sun 형식으로 입력해주세요.")
