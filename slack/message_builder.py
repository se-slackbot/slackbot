from datetime import datetime, date
from zoneinfo import ZoneInfo

from weather.formatter import format_weather_fields, get_weather_emoji
from schedule.formatter import format_course_list

VERSION = "v1.0"


def build_daily_message(weather: dict, courses: list[dict], timezone: str = "Asia/Seoul") -> list[dict]:
    tz = ZoneInfo(timezone)
    now = datetime.now(tz)
    today_str = now.strftime("%Y년 %m월 %d일 (%a)")
    updated_str = now.strftime("%H:%M")

    emoji = get_weather_emoji(weather["weather_id"])

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} 오늘의 날씨 & 강의 일정 — {today_str}",
            },
        },
        {
            "type": "section",
            "fields": format_weather_fields(weather),
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:books: 오늘의 강의*\n{format_course_list(courses)}",
            },
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"마지막 업데이트: {updated_str} | {VERSION}",
                }
            ],
        },
    ]
    return blocks


def build_weather_message(weather: dict) -> list[dict]:
    emoji = get_weather_emoji(weather["weather_id"])
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{emoji} {weather['city']} 현재 날씨*"},
            "fields": format_weather_fields(weather),
        }
    ]


def build_schedule_message(courses: list[dict], label: str = "오늘") -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*:books: {label} 강의*\n{format_course_list(courses)}",
            },
        }
    ]


def build_help_message() -> list[dict]:
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*:robot_face: Slack Weather & Schedule Bot 도움말*\n\n"
                    "• `/날씨 [도시명]` — 실시간 날씨 조회 (기본: 설정된 도시)\n"
                    "• `/시간표 [오늘|내일|YYYY-MM-DD]` — 강의 목록 조회\n"
                    "• `/시간표 추가 <요일> <시작> <종료> <과목명> [장소] [교수] [메모]` — 개인 시간표 추가\n"
                    "• `/설정 [도시] [HH:MM]` — 위치 및 알림 시각 변경\n"
                    "• `/도움말` — 이 메시지 표시"
                ),
            },
        }
    ]
