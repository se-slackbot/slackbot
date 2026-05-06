"""slack/message_builder.py 테스트"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from slack.message_builder import (
    build_weather_message,
    build_schedule_message,
    build_daily_message,
    build_help_message,
)


@pytest.fixture
def weather():
    return {
        "city": "Seoul",
        "weather_id": 800,
        "description": "맑음",
        "temp": 20,
        "feels_like": 18,
        "rain_prob": 5,
        "humidity": 60,
    }


@pytest.fixture
def courses():
    return [
        {"course_name": "알고리즘", "start_time": "10:30", "end_time": "12:00",
         "room": "공학관 401호", "professor": "박교수"},
    ]


class TestBuildWeatherMessage:
    def test_블록_리스트_반환(self, weather):
        blocks = build_weather_message(weather)
        assert isinstance(blocks, list)
        assert len(blocks) > 0

    def test_section_타입_포함(self, weather):
        blocks = build_weather_message(weather)
        types = [b["type"] for b in blocks]
        assert "section" in types

    def test_도시명_포함(self, weather):
        blocks = build_weather_message(weather)
        text = str(blocks)
        assert "Seoul" in text


class TestBuildScheduleMessage:
    def test_강의_있는_경우(self, courses):
        blocks = build_schedule_message(courses, "오늘")
        assert isinstance(blocks, list)
        text = str(blocks)
        assert "알고리즘" in text

    def test_강의_없는_경우(self):
        blocks = build_schedule_message([], "오늘")
        assert isinstance(blocks, list)
        text = str(blocks)
        assert "강의가 없습니다" in text

    def test_레이블_포함(self, courses):
        blocks = build_schedule_message(courses, "내일")
        text = str(blocks)
        assert "내일" in text


class TestBuildDailyMessage:
    def test_헤더_포함(self, weather, courses):
        blocks = build_daily_message(weather, courses)
        types = [b["type"] for b in blocks]
        assert "header" in types

    def test_구분선_포함(self, weather, courses):
        blocks = build_daily_message(weather, courses)
        types = [b["type"] for b in blocks]
        assert "divider" in types

    def test_컨텍스트_버전_포함(self, weather, courses):
        blocks = build_daily_message(weather, courses)
        text = str(blocks)
        assert "v1.0" in text

    def test_날씨_정보_포함(self, weather, courses):
        blocks = build_daily_message(weather, courses)
        text = str(blocks)
        assert "20°C" in text

    def test_강의_정보_포함(self, weather, courses):
        blocks = build_daily_message(weather, courses)
        text = str(blocks)
        assert "알고리즘" in text


class TestBuildHelpMessage:
    def test_블록_반환(self):
        blocks = build_help_message()
        assert isinstance(blocks, list)
        assert len(blocks) > 0

    def test_슬래시_커맨드_안내_포함(self):
        blocks = build_help_message()
        text = str(blocks)
        assert "/날씨" in text
        assert "/시간표" in text
        assert "/설정" in text
        assert "/도움말" in text
