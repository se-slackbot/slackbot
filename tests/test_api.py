import pytest

from fastapi import HTTPException

from api import _build_ics, _verify_calendar_token


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
    courses = [
        {
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
    ]

    first = _build_ics(courses)
    second = _build_ics(courses)

    assert first == second
    assert b"UID:" in first
