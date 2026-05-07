"""scheduler.py 테스트"""
import os
import sqlite3
import sys
import tempfile
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config_store import ConfigStore
from schedule.repository import add_course, init_db
from scheduler import (
    _run_user_daily_brief,
    _run_due_user_briefs,
    _sent_user_briefs,
    create_scheduler,
)


def _make_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    return path


def test_create_scheduler_사용자별_due_check_job_등록():
    db_path = _make_db()
    try:
        store = ConfigStore(db_path)
        scheduler = create_scheduler(
            MagicMock(),
            "C_CHANNEL",
            "api-key",
            db_path,
            "Seoul",
            "07:00",
            store,
        )
        assert scheduler.get_job("daily_brief") is not None
        assert scheduler.get_job("user_daily_briefs") is not None
    finally:
        os.unlink(db_path)


def test_run_user_daily_brief_사용자_도시와_개인_시간표로_DM_전송():
    db_path = _make_db()
    try:
        store = ConfigStore(db_path)
        store.set("U_001", city="Busan", notify_time="08:30", timezone="Asia/Seoul")
        add_course(db_path, "U_001", "자료구조", "Mon", "09:00", "10:00", "101")
        app = MagicMock()

        with patch("scheduler.fetch_weather") as fetch_weather, patch("scheduler.datetime") as mock_datetime:
            fetch_weather.return_value = {
                "city": "Busan",
                "weather_id": 800,
                "description": "맑음",
                "temp": 20,
                "feels_like": 18,
                "rain_prob": 5,
                "humidity": 60,
            }
            mock_datetime.now.return_value.date.return_value.weekday.return_value = 0
            _run_user_daily_brief(app, store.get("U_001"), "api-key", db_path)

        fetch_weather.assert_called_once_with("Busan", "api-key")
        call = app.client.chat_postMessage.call_args[1]
        assert call["channel"] == "U_001"
        assert "자료구조" in str(call["blocks"])
    finally:
        os.unlink(db_path)


def test_run_due_user_briefs_같은_분에는_중복_전송하지_않음():
    db_path = _make_db()
    try:
        store = ConfigStore(db_path)
        store.set("U_001", city="Seoul", notify_time="07:00")
        app = MagicMock()
        _sent_user_briefs.clear()

        with patch("scheduler._is_user_brief_due", return_value=True), patch("scheduler._user_brief_key", return_value=("U_001", "2026-05-06", "07:00")), patch("scheduler._run_user_daily_brief") as run_brief:
            _run_due_user_briefs(app, store, "api-key", db_path)
            _run_due_user_briefs(app, store, "api-key", db_path)

        run_brief.assert_called_once()
    finally:
        _sent_user_briefs.clear()
        os.unlink(db_path)
