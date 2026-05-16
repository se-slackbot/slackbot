from __future__ import annotations
import uuid
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response

from schedule.repository import get_all_courses_for_user

DAY_TO_RRULE = {
    "Mon": "MO", "Tue": "TU", "Wed": "WE", "Thu": "TH",
    "Fri": "FR", "Sat": "SA", "Sun": "SU",
}
DAY_TO_WEEKDAY = {
    "Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6,
}


def _next_weekday(d: date, weekday: int) -> date:
    days_ahead = weekday - d.weekday()
    if days_ahead < 0:
        days_ahead += 7
    return d + timedelta(days=days_ahead)


def _build_ics(courses: list[dict]) -> bytes:
    from icalendar import Calendar, Event

    cal = Calendar()
    cal.add("prodid", "-//Slackbot//KR")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "강의 시간표")
    cal.add("x-wr-timezone", "Asia/Seoul")

    tz = ZoneInfo("Asia/Seoul")
    today = date.today()

    for course in courses:
        day = course["day_of_week"]
        rrule_day = DAY_TO_RRULE.get(day)
        weekday_num = DAY_TO_WEEKDAY.get(day)
        if rrule_day is None or weekday_num is None:
            continue

        sh, sm = map(int, course["start_time"].split(":"))
        eh, em = map(int, course["end_time"].split(":"))
        event_date = _next_weekday(today, weekday_num)

        event = Event()
        event.add("summary", course["course_name"])
        event.add("dtstart", datetime(event_date.year, event_date.month, event_date.day, sh, sm, tzinfo=tz))
        event.add("dtend",   datetime(event_date.year, event_date.month, event_date.day, eh, em, tzinfo=tz))
        event.add("rrule", {"freq": "weekly", "byday": [rrule_day]})
        event.add("uid", str(uuid.uuid4()))

        if course.get("room"):
            event.add("location", course["room"])

        desc_parts = []
        if course.get("professor"):
            desc_parts.append(f"교수: {course['professor']}")
        if course.get("memo"):
            desc_parts.append(f"메모: {course['memo']}")
        if desc_parts:
            event.add("description", "\n".join(desc_parts))

        cal.add_component(event)

    return cal.to_ical()


def create_api() -> FastAPI:
    app = FastAPI(title="Slackbot Calendar API")

    @app.get("/calendar/{slack_user_id}.ics", summary="강의 시간표 ICS 다운로드")
    def get_calendar(slack_user_id: str):
        try:
            courses = get_all_courses_for_user(slack_user_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

        ics_bytes = _build_ics(courses)
        return Response(
            content=ics_bytes,
            media_type="text/calendar; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={slack_user_id}.ics"},
        )

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app
