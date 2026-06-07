from datetime import datetime
from zoneinfo import ZoneInfo

from bot.courses import DAYS

VERSION = "v1.0"

DAY_KR = dict(zip(DAYS, "월화수목금토일"))

# OpenWeather condition code 의 앞자리로 분류한다. 800(맑음)만 801~804(구름)와 갈라진다.
WEATHER_EMOJI = {
    2: ":thunder_cloud_and_rain:",
    3: ":barely_sunny:",
    5: ":rain_cloud:",
    6: ":snowflake:",
    7: ":fog:",
    8: ":partly_sunny:",
}


def get_weather_emoji(weather_id: int) -> str:
    if weather_id == 800:
        return ":sunny:"
    return WEATHER_EMOJI.get(weather_id // 100, ":white_sun_cloud:")


def format_weather_fields(weather: dict) -> list[dict]:
    emoji = get_weather_emoji(weather["weather_id"])
    return [
        {"type": "mrkdwn", "text": f"*날씨*\n{emoji} {weather['description']}"},
        {"type": "mrkdwn", "text": f"*기온*\n{weather['temp']}°C (체감 {weather['feels_like']}°C)"},
        {"type": "mrkdwn", "text": f"*강수 확률*\n{weather['rain_prob']}%"},
        {"type": "mrkdwn", "text": f"*습도*\n{weather['humidity']}%"},
    ]


HELP_TEXT = (
    "*:robot_face: Slack Weather & Schedule Bot 도움말*\n\n"
    "• `/weather`, `/날씨 [도시명]` — 실시간 날씨 조회 (기본: 설정된 도시)\n"
    "• `/schedule`, `/시간표 [오늘|내일|YYYY-MM-DD]` — 강의 목록 조회\n"
    "• `/schedule 추가`, `/시간표 추가 <요일> <시작> <종료> <과목명> [장소] [교수] [메모]` — 개인 시간표 추가\n"
    "• `/schedule 수정`, `/시간표 수정 <ID> <field=value>...` — 개인 시간표 수정\n"
    "• `/schedule 삭제`, `/시간표 삭제 <ID>` — 개인 시간표 삭제\n"
    "• `/schedule 목록`, `/시간표 목록` — 등록한 개인 일정과 ID 조회\n"
    "• `/config`, `/설정 [도시] [HH:MM] [timezone]` — 위치, 알림 시각, 타임존 변경\n"
    "• `/브리핑`, `/brief` — 날씨 + 시간표 + 캘린더 즉시 조회\n"
    "• `/bot-help`, `/도움말` — 이 메시지 표시"
)


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text}}


def _format_courses(courses: list[dict]) -> str:
    if not courses:
        return "오늘은 강의가 없습니다. :tada:"
    return "\n".join(
        f"• *{c['start_time']} ~ {c['end_time']}*  {c['course_name']}"
        + (f" | {c['room']}" if c.get("room") else "")
        for c in courses
    )


def build_daily_message(
    weather: dict,
    courses: list[dict],
    timezone: str = "Asia/Seoul",
    calendar_events: list[dict] | None = None,
) -> list[dict]:
    now = datetime.now(ZoneInfo(timezone))
    emoji = get_weather_emoji(weather["weather_id"])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} 오늘의 날씨 & 강의 일정 — {now:%Y년 %m월 %d일 (%a)}",
            },
        },
        {"type": "section", "fields": format_weather_fields(weather)},
        {"type": "divider"},
        _section(f"*:books: 오늘의 강의*\n{_format_courses(courses)}"),
    ]

    if calendar_events:
        lines = "\n".join(
            f"`{e['time']}`  *{e['summary']}*" + (f"  _{e['location']}_" if e.get("location") else "")
            for e in calendar_events
        )
        blocks += [{"type": "divider"}, _section(f":calendar: *오늘의 일정*\n{lines}")]

    blocks.append({
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": f"마지막 업데이트: {now:%H:%M} | {VERSION}"}],
    })
    return blocks


def build_weather_message(weather: dict) -> list[dict]:
    emoji = get_weather_emoji(weather["weather_id"])
    return [{
        **_section(f"*{emoji} {weather['city']} 현재 날씨*"),
        "fields": format_weather_fields(weather),
    }]


def build_schedule_message(courses: list[dict], label: str = "오늘") -> list[dict]:
    return [_section(f"*:books: {label} 강의*\n{_format_courses(courses)}")]


def build_course_list_message(courses: list[dict]) -> list[dict]:
    """수정·삭제에 쓸 ID를 함께 보여주는 개인 일정 목록."""
    if not courses:
        return [_section("*:books: 내 개인 일정*\n등록한 개인 일정이 없습니다. `/시간표 추가`로 등록하세요.")]
    lines = "\n".join(
        f"• `{c['id']}`  *{DAY_KR.get(c['day_of_week'], c['day_of_week'])}* "
        f"{c['start_time']}~{c['end_time']}  {c['course_name']}"
        + (f" | {c['room']}" if c.get("room") else "")
        for c in courses
    )
    return [_section(f"*:books: 내 개인 일정*\n{lines}\n\n_수정·삭제는 앞의 ID를 사용합니다._")]


def build_help_message() -> list[dict]:
    return [_section(HELP_TEXT)]
