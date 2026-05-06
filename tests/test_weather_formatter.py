"""weather/formatter.py 테스트"""
import pytest
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from weather.formatter import get_weather_emoji, format_weather_fields


class TestGetWeatherEmoji:
    @pytest.mark.parametrize("weather_id,expected", [
        (200, ":thunder_cloud_and_rain:"),
        (232, ":thunder_cloud_and_rain:"),
        (300, ":barely_sunny:"),
        (321, ":barely_sunny:"),
        (500, ":rain_cloud:"),
        (531, ":rain_cloud:"),
        (600, ":snowflake:"),
        (622, ":snowflake:"),
        (701, ":fog:"),
        (781, ":fog:"),
        (800, ":sunny:"),
        (801, ":partly_sunny:"),
        (804, ":partly_sunny:"),
        (900, ":white_sun_cloud:"),  # 미정의 코드
    ])
    def test_날씨코드별_이모지(self, weather_id, expected):
        assert get_weather_emoji(weather_id) == expected


class TestFormatWeatherFields:
    @pytest.fixture
    def weather(self):
        return {
            "weather_id": 800,
            "description": "맑음",
            "temp": 22,
            "feels_like": 20,
            "rain_prob": 10,
            "humidity": 55,
        }

    def test_필드_4개_반환(self, weather):
        fields = format_weather_fields(weather)
        assert len(fields) == 4

    def test_모든_필드_mrkdwn_타입(self, weather):
        fields = format_weather_fields(weather)
        assert all(f["type"] == "mrkdwn" for f in fields)

    def test_기온_포함(self, weather):
        fields = format_weather_fields(weather)
        texts = " ".join(f["text"] for f in fields)
        assert "22°C" in texts
        assert "20°C" in texts

    def test_강수확률_포함(self, weather):
        fields = format_weather_fields(weather)
        texts = " ".join(f["text"] for f in fields)
        assert "10%" in texts

    def test_습도_포함(self, weather):
        fields = format_weather_fields(weather)
        texts = " ".join(f["text"] for f in fields)
        assert "55%" in texts
