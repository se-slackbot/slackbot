import logging
import time
import requests

logger = logging.getLogger(__name__)

OPENWEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"

# 1시간 TTL 캐시
_cache: dict = {}
CACHE_TTL = 3600


def _is_cache_valid(key: str) -> bool:
    if key not in _cache:
        return False
    return time.time() - _cache[key]["timestamp"] < CACHE_TTL


def _has_cache(key: str) -> bool:
    return key in _cache


def fetch_weather(city: str, api_key: str) -> dict:
    cache_key = f"weather:{city}"
    if _is_cache_valid(cache_key):
        logger.warning("날씨 캐시 사용: %s", city)
        return _cache[cache_key]["data"]

    try:
        resp = requests.get(
            OPENWEATHER_URL,
            params={"q": city, "appid": api_key, "units": "metric", "lang": "kr"},
            timeout=10,
        )
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
        if _has_cache(cache_key):
            logger.warning("만료된 캐시 사용: %s", city)
            return _cache[cache_key]["data"]
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
