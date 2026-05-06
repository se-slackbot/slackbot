"""weather/fetcher.py 테스트"""
import time
import pytest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from weather.fetcher import fetch_weather, _fetch_rain_probability, _cache, CACHE_TTL


WEATHER_RESPONSE = {
    "name": "Seoul",
    "main": {"temp": 18.4, "feels_like": 16.9, "humidity": 65},
    "weather": [{"id": 800, "description": "맑음"}],
}

FORECAST_RESPONSE = {
    "list": [{"pop": 0.2}]
}


@pytest.fixture(autouse=True)
def clear_cache():
    _cache.clear()
    yield
    _cache.clear()


class TestFetchWeather:
    def test_정상_날씨_반환(self, requests_mock):
        requests_mock.get("https://api.openweathermap.org/data/2.5/weather", json=WEATHER_RESPONSE)
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", json=FORECAST_RESPONSE)

        result = fetch_weather("Seoul", "FAKE_KEY")

        assert result["city"] == "Seoul"
        assert result["temp"] == 18
        assert result["feels_like"] == 17
        assert result["humidity"] == 65
        assert result["weather_id"] == 800
        assert result["description"] == "맑음"
        assert result["rain_prob"] == 20

    def test_캐시_TTL_이내_재사용(self, requests_mock):
        requests_mock.get("https://api.openweathermap.org/data/2.5/weather", json=WEATHER_RESPONSE)
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", json=FORECAST_RESPONSE)

        fetch_weather("Seoul", "FAKE_KEY")
        fetch_weather("Seoul", "FAKE_KEY")

        assert requests_mock.call_count == 2  # weather + forecast (1회만 호출)

    def test_API_실패시_예외_발생(self, requests_mock):
        import requests as req
        requests_mock.get("https://api.openweathermap.org/data/2.5/weather", exc=req.RequestException("timeout"))

        with pytest.raises(req.RequestException):
            fetch_weather("InvalidCity", "FAKE_KEY")

    def test_API_실패시_유효캐시_반환(self, requests_mock):
        """API 실패 시 TTL 이내 캐시가 있으면 해당 캐시 반환"""
        import requests as req
        _cache["weather:Seoul"] = {
            "data": {"city": "Seoul", "temp": 15, "feels_like": 13, "humidity": 70,
                     "weather_id": 800, "description": "맑음", "rain_prob": 10},
            "timestamp": time.time(),  # 아직 유효한 캐시
        }
        requests_mock.get("https://api.openweathermap.org/data/2.5/weather", exc=req.RequestException("timeout"))

        # 첫 fetch에서 캐시 히트 → API 호출 없이 반환
        result = fetch_weather("Seoul", "FAKE_KEY")
        assert result["temp"] == 15

    def test_API_실패_만료_캐시_없는_경우_예외_발생(self, requests_mock):
        """API 실패이고 캐시도 만료됐으면 예외를 그대로 올림"""
        import requests as req
        _cache["weather:Seoul"] = {
            "data": {"city": "Seoul", "temp": 15, "feels_like": 13, "humidity": 70,
                     "weather_id": 800, "description": "맑음", "rain_prob": 10},
            "timestamp": time.time() - CACHE_TTL - 1,  # 만료된 캐시
        }
        requests_mock.get("https://api.openweathermap.org/data/2.5/weather", exc=req.RequestException("timeout"))

        with pytest.raises(req.RequestException):
            fetch_weather("Seoul", "FAKE_KEY")

    def test_기온_반올림_정수_반환(self, requests_mock):
        resp = {**WEATHER_RESPONSE, "main": {"temp": 18.6, "feels_like": 16.3, "humidity": 60}}
        requests_mock.get("https://api.openweathermap.org/data/2.5/weather", json=resp)
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", json=FORECAST_RESPONSE)

        result = fetch_weather("Seoul", "FAKE_KEY")
        assert result["temp"] == 19
        assert result["feels_like"] == 16


class TestFetchRainProbability:
    def test_정상_강수확률_반환(self, requests_mock):
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", json=FORECAST_RESPONSE)

        result = _fetch_rain_probability("Seoul", "FAKE_KEY")
        assert result == 20

    def test_강수확률_없는_경우_0_반환(self, requests_mock):
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", json={"list": [{}]})

        result = _fetch_rain_probability("Seoul", "FAKE_KEY")
        assert result == 0

    def test_API_실패시_0_반환(self, requests_mock):
        import requests as req
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", exc=req.RequestException)

        result = _fetch_rain_probability("Seoul", "FAKE_KEY")
        assert result == 0

    def test_강수확률_100퍼센트(self, requests_mock):
        requests_mock.get("https://api.openweathermap.org/data/2.5/forecast", json={"list": [{"pop": 1.0}]})

        result = _fetch_rain_probability("Seoul", "FAKE_KEY")
        assert result == 100
