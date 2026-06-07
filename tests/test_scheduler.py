"""bot/scheduler.py 테스트"""
import os
import tempfile
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import requests

from bot.config_store import ConfigStore
from bot.courses import add_course, init_db
from bot.scheduler import (
    COLLECT_BACKOFF,
    LAST_BRIEF_KEY,
    _run_due_user_briefs,
    _stop_job_on_invalid_key,
    create_scheduler,
    run_brief,
)
from bot.weather import InvalidAPIKey


def _make_db():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    return path


def test_create_scheduler_사용자별_due_check_job_등록():
    db_path = _make_db()
    try:
        scheduler = create_scheduler(
            MagicMock(), "C_CHANNEL", "api-key", db_path, "Seoul", "07:00", ConfigStore(db_path)
        )
        assert scheduler.get_job("daily_brief") is not None
        assert scheduler.get_job("user_daily_briefs") is not None
    finally:
        os.unlink(db_path)


def test_run_brief_사용자_도시와_개인_시간표로_DM_전송():
    db_path = _make_db()
    try:
        store = ConfigStore(db_path)
        store.set("U_001", city="Busan", notify_time="08:30", timezone="Asia/Seoul")
        add_course(db_path, "U_001", "자료구조", "Mon", "09:00", "10:00", "101")
        app = MagicMock()

        with patch("bot.scheduler.fetch_weather") as fetch_weather, patch("bot.scheduler.datetime") as mock_datetime:
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
            assert run_brief(app, "U_001", "api-key", db_path, "Busan", "Asia/Seoul", "U_001") is True

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

        with patch("bot.scheduler._due_key", return_value="2026-05-06 07:00"), patch(
            "bot.scheduler.run_brief", return_value=True
        ) as run:
            _run_due_user_briefs(app, store, "api-key", db_path)
            # 프로세스 재시작 = 새 ConfigStore. 발송 기록이 DB 에 있어야 다시 보내지 않는다.
            _run_due_user_briefs(app, ConfigStore(db_path), "api-key", db_path)

        run.assert_called_once()
        assert store.get("U_001")["settings"][LAST_BRIEF_KEY] == "2026-05-06 07:00"
    finally:
        os.unlink(db_path)


def test_run_due_user_briefs_전송_실패는_기록하지_않음():
    db_path = _make_db()
    try:
        store = ConfigStore(db_path)
        store.set("U_001", city="Seoul", notify_time="07:00")

        with patch("bot.scheduler._due_key", return_value="2026-05-06 07:00"), patch(
            "bot.scheduler.run_brief", return_value=False
        ):
            _run_due_user_briefs(MagicMock(), store, "api-key", db_path)

        assert LAST_BRIEF_KEY not in store.get("U_001")["settings"]
    finally:
        os.unlink(db_path)


def test_run_brief_키_오류는_채널에_알리고_위로_올린다():
    db_path = _make_db()
    try:
        app = MagicMock()
        with patch("bot.scheduler.fetch_weather", side_effect=InvalidAPIKey("키 거부")):
            with pytest.raises(InvalidAPIKey):
                run_brief(app, "C_CHANNEL", "bad-key", db_path, "Seoul")

        assert ":rotating_light:" in app.client.chat_postMessage.call_args[1]["text"]
    finally:
        os.unlink(db_path)


def test_run_due_user_briefs_키_오류는_잡_전체를_멈춘다():
    db_path = _make_db()
    try:
        store = ConfigStore(db_path)
        store.set("U_001", city="Seoul", notify_time="07:00")

        with patch("bot.scheduler._due_key", return_value="2026-05-06 07:00"), patch(
            "bot.scheduler.run_brief", side_effect=InvalidAPIKey("키 거부")
        ):
            with pytest.raises(InvalidAPIKey):
                _run_due_user_briefs(MagicMock(), store, "api-key", db_path)
    finally:
        os.unlink(db_path)


def test_stop_job_on_invalid_key_키_오류만_잡을_제거():
    scheduler = MagicMock()
    listener = _stop_job_on_invalid_key(scheduler)

    listener(SimpleNamespace(exception=RuntimeError("일시 오류"), job_id="daily_brief"))
    scheduler.remove_job.assert_not_called()

    listener(SimpleNamespace(exception=InvalidAPIKey("키 거부"), job_id="user_daily_briefs"))
    scheduler.remove_job.assert_called_once_with("user_daily_briefs")


def test_due_key_알림_시각이_아니면_None():
    from bot.scheduler import _due_key

    with patch("bot.scheduler.datetime") as mock_datetime:
        mock_datetime.now.return_value.__format__ = lambda _self, spec: {
            "%Y-%m-%d": "2026-05-06",
            "%H:%M": "07:00",
        }[spec]
        assert _due_key({"notify_time": "07:00", "timezone": "Asia/Seoul"}) == "2026-05-06 07:00"
        assert _due_key({"notify_time": "09:30", "timezone": "Asia/Seoul"}) is None


def test_run_brief_일시적_수집_오류는_재시도한다():
    db_path = _make_db()
    try:
        app = MagicMock()
        weather = {
            "city": "Seoul",
            "weather_id": 800,
            "description": "맑음",
            "temp": 20,
            "feels_like": 18,
            "rain_prob": 5,
            "humidity": 60,
        }
        with patch("bot.scheduler.time.sleep") as sleep, patch(
            "bot.scheduler.fetch_weather",
            side_effect=[requests.RequestException("일시 오류"), weather],
        ) as fetch:
            assert run_brief(app, "C_CHANNEL", "api-key", db_path, "Seoul") is True

        assert fetch.call_count == 2
        sleep.assert_called_once_with(COLLECT_BACKOFF[0])
        # 오류 알림 없이 브리프만 나간다
        assert ":rotating_light:" not in str(app.client.chat_postMessage.call_args_list)
    finally:
        os.unlink(db_path)


def test_run_brief_재시도_소진되면_실패():
    db_path = _make_db()
    try:
        app = MagicMock()
        with patch("bot.scheduler.time.sleep"), patch(
            "bot.scheduler.fetch_weather", side_effect=requests.RequestException("일시 오류")
        ) as fetch:
            assert run_brief(app, "C_CHANNEL", "api-key", db_path, "Seoul") is False

        assert fetch.call_count == len(COLLECT_BACKOFF) + 1
        assert ":rotating_light:" in app.client.chat_postMessage.call_args[1]["text"]
    finally:
        os.unlink(db_path)


def test_수집_재시도_총_대기는_매분_잡_주기를_넘지_않는다():
    assert sum(COLLECT_BACKOFF) < 60
