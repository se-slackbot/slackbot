from __future__ import annotations
import os
import secrets
import uuid
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from icalendar import Calendar, Event

from bot.courses import DAYS, get_all_courses_for_user

SEOUL = ZoneInfo("Asia/Seoul")


def create_api() -> FastAPI:
    app = FastAPI(title="Slackbot Calendar API")

    @app.get("/calendar/{slack_user_id}.ics", summary="강의 시간표 ICS 다운로드")
    def get_calendar(slack_user_id: str, token: str = Query(default="")):
        _verify_calendar_token(token)
        try:
            courses = get_all_courses_for_user(slack_user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        return Response(
            content=_build_ics(courses),
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={_safe_filename(slack_user_id)}.ics"},
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def _build_ics(courses: list[dict]) -> bytes:
    cal = Calendar()
    cal.add("prodid", "-//Slackbot//KR")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "강의 시간표")
    cal.add("x-wr-timezone", "Asia/Seoul")

    today = datetime.now(SEOUL).date()  # 서버 로컬 날짜면 UTC 서버에서 하루 어긋난다
    for course in courses:
        day = course["day_of_week"]
        if day not in DAYS:
            continue
        # 이번 주(또는 다음 주)의 해당 요일부터 매주 반복
        event_date = today + timedelta(days=(DAYS.index(day) - today.weekday()) % 7)

        event = Event()
        event.add("summary", course["course_name"])
        event.add("dtstart", _at(event_date, course["start_time"]))
        event.add("dtend", _at(event_date, course["end_time"]))
        event.add("rrule", {"freq": "weekly", "byday": [day[:2].upper()]})
        event.add("uid", str(uuid.uuid5(uuid.NAMESPACE_URL, f"slackbot:{course['slack_user_id']}:{course['id']}")))

        if course.get("room"):
            event.add("location", course["room"])
        description = "\n".join(
            f"{label}: {course[key]}" for key, label in (("professor", "교수"), ("memo", "메모")) if course.get(key)
        )
        if description:
            event.add("description", description)

        cal.add_component(event)

    return cal.to_ical()


def _at(day: date, hhmm: str) -> datetime:
    return datetime.combine(day, time.fromisoformat(hhmm), SEOUL)


def _verify_calendar_token(token: str) -> None:
    expected = os.getenv("CALENDAR_ACCESS_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="Calendar access token is not configured")
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Invalid calendar access token")


def _safe_filename(value: str) -> str:
    return "".join(ch for ch in value if ch.isalnum() or ch in ("-", "_")) or "calendar"
