import logging
import time
import requests

logger = logging.getLogger(__name__)

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# 1시간 TTL 캐시
_cache: dict = {}
CACHE_TTL = 3600


class InvalidAPIKey(Exception):
    """OpenWeather 가 키를 거부했다(401). RequestException 이 아니므로 캐시 폴백을 타지 않는다."""


def fetch_weather(city: str, api_key: str) -> dict:
    cache_key = f"weather:{city}"
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["timestamp"] < CACHE_TTL:
        logger.warning("날씨 캐시 사용: %s", city)
        return cached["data"]

    try:
        resp = requests.get(
            OPENWEATHER_URL,
            params={"q": city, "appid": api_key, "units": "metric", "lang": "kr"},
            timeout=10,
        )
        if resp.status_code == 401:
            raise InvalidAPIKey("OpenWeather API 키가 거부되었습니다(401). 키를 고치고 봇을 재시작하세요")
        resp.raise_for_status()
        data = resp.json()
        logger.debug("날씨 API 응답: %s", data)

        rain_prob = _fetch_rain_probability(city, api_key)
        result = {
            "city": data.get("name", city),
            "temp": round(data["main"]["temp"]),
            "feels_like": round(data["main"]["feels_like"]),
            "humidity": data["main"]["humidity"],
            "weather_id": data["weather"][0]["id"],
            "description": data["weather"][0]["description"],
            "rain_prob": rain_prob,
        }
        _cache[cache_key] = {"data": result, "timestamp": time.time()}
        return result

    except requests.RequestException as e:
        logger.error("날씨 API 호출 실패: %s", e)
        if cached:
            logger.warning("만료된 캐시 사용: %s", city)
            return cached["data"]
        raise


def _fetch_rain_probability(city: str, api_key: str) -> int:
    try:
        resp = requests.get(
            FORECAST_URL,
            params={"q": city, "appid": api_key, "units": "metric", "cnt": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        pop = data["list"][0].get("pop", 0)
        return round(pop * 100)
    except Exception:
        return 0
