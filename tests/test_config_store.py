"""config_store.py 테스트"""
import pytest
import tempfile
import os
import sqlite3

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from config_store import ConfigStore, DEFAULT_CONFIG


@pytest.fixture
def store():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    s = ConfigStore(path)
    yield s
    os.unlink(path)


class TestConfigStoreGet:
    def test_미등록_유저_기본값_반환(self, store):
        config = store.get("U_NEW_USER")
        assert config["city"] == DEFAULT_CONFIG["city"]
        assert config["notify_time"] == DEFAULT_CONFIG["notify_time"]
        assert config["timezone"] == DEFAULT_CONFIG["timezone"]

    def test_미등록_유저_slack_user_id_포함(self, store):
        config = store.get("U_ABC123")
        assert config["slack_user_id"] == "U_ABC123"

    def test_저장된_설정_정확히_반환(self, store):
        store.set("U_001", city="Busan", notify_time="08:30")
        config = store.get("U_001")
        assert config["city"] == "Busan"
        assert config["region"] == "Busan"
        assert config["notify_time"] == "08:30"


class TestConfigStoreSet:
    def test_신규_유저_설정_저장(self, store):
        store.set("U_NEW", city="Daegu", notify_time="06:00")
        config = store.get("U_NEW")
        assert config["city"] == "Daegu"
        assert config["notify_time"] == "06:00"

    def test_기존_유저_설정_업데이트(self, store):
        store.set("U_001", city="Seoul", notify_time="07:00")
        store.set("U_001", city="Incheon", notify_time="09:00")
        config = store.get("U_001")
        assert config["city"] == "Incheon"
        assert config["notify_time"] == "09:00"

    def test_도시만_업데이트_시간_유지(self, store):
        store.set("U_001", city="Seoul", notify_time="07:30")
        store.set("U_001", city="Gwangju")
        config = store.get("U_001")
        assert config["city"] == "Gwangju"
        assert config["notify_time"] == "07:30"

    def test_시간만_업데이트_도시_유지(self, store):
        store.set("U_001", city="Busan", notify_time="07:00")
        store.set("U_001", notify_time="10:00")
        config = store.get("U_001")
        assert config["city"] == "Busan"
        assert config["notify_time"] == "10:00"

    def test_여러_유저_독립_저장(self, store):
        store.set("U_A", city="Seoul", notify_time="07:00")
        store.set("U_B", city="Busan", notify_time="08:00")
        assert store.get("U_A")["city"] == "Seoul"
        assert store.get("U_B")["city"] == "Busan"

    def test_DB_테이블_초기화(self, store):
        with sqlite3.connect(store.db_path) as conn:
            tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "user_config" in tables

    def test_지역과_타임존_설정_JSON_저장(self, store):
        store.set(
            "U_SETTINGS",
            region="Jeju",
            timezone="Asia/Seoul",
            settings={"daily_brief": True, "language": "ko"},
        )
        config = store.get("U_SETTINGS")
        assert config["city"] == "Jeju"
        assert config["region"] == "Jeju"
        assert config["timezone"] == "Asia/Seoul"
        assert config["settings"] == {"daily_brief": True, "language": "ko"}

    def test_설정_JSON_부분_업데이트(self, store):
        store.set("U_SETTINGS", settings={"daily_brief": True, "language": "ko"})
        store.set("U_SETTINGS", settings={"language": "en"})
        config = store.get("U_SETTINGS")
        assert config["settings"] == {"daily_brief": True, "language": "en"}
