import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from fastapi import HTTPException

from bot.api import SEOUL, _build_ics, _verify_calendar_token
from bot.courses import DAYS

MONDAY_COURSE = {
    "id": 1,
    "slack_user_id": "U_001",
    "course_name": "알고리즘",
    "day_of_week": "Mon",
    "start_time": "09:00",
    "end_time": "10:30",
    "room": "101",
    "professor": "박교수",
    "memo": "",
}


def test_calendar_endpoint_requires_access_token(monkeypatch):
    monkeypatch.setenv("CALENDAR_ACCESS_TOKEN", "secret-token")

    with pytest.raises(HTTPException) as exc:
        _verify_calendar_token("")
    assert exc.value.status_code == 403


def test_calendar_endpoint_requires_configured_token(monkeypatch):
    monkeypatch.delenv("CALENDAR_ACCESS_TOKEN", raising=False)

    with pytest.raises(HTTPException) as exc:
        _verify_calendar_token("secret-token")
    assert exc.value.status_code == 503


def test_build_ics_uses_stable_uid():
    courses = [MONDAY_COURSE]

    first = _build_ics(courses)
    second = _build_ics(courses)

    assert first == second
    assert b"UID:" in first


def _tz_with_other_date(seoul_today) -> str:
    """지금 서울과 날짜가 다른 타임존. UTC-12 / UTC+14 중 하나는 항상 다르다."""
    return next(
        tz for tz in ("Etc/GMT+12", "Pacific/Kiritimati")
        if datetime.now(ZoneInfo(tz)).date() != seoul_today
    )


def test_build_ics_dtstart_은_서울_날짜_기준(monkeypatch):
    """서버 로컬 날짜로 잡으면 요일 하나의 첫 회차가 한 주 어긋난다."""
    seoul_today = datetime.now(SEOUL).date()
    monkeypatch.setenv("TZ", _tz_with_other_date(seoul_today))
    time.tzset()
    try:
        # 어긋나는 요일은 서버와 서울의 날짜 차이에 따라 달라지므로 7요일을 모두 넣는다.
        ics = _build_ics([{**MONDAY_COURSE, "id": i, "day_of_week": d} for i, d in enumerate(DAYS)])

        for day in DAYS:
            expected = seoul_today + timedelta(days=(DAYS.index(day) - seoul_today.weekday()) % 7)
            assert f"DTSTART;TZID=Asia/Seoul:{expected:%Y%m%d}T090000".encode() in ics
    finally:
        monkeypatch.undo()
        time.tzset()
