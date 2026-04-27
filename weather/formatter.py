WEATHER_EMOJI_MAP = [
    (range(200, 233), ":thunder_cloud_and_rain:"),
    (range(300, 322), ":barely_sunny:"),
    (range(500, 532), ":rain_cloud:"),
    (range(600, 623), ":snowflake:"),
    (range(700, 782), ":fog:"),
    (range(800, 801), ":sunny:"),
    (range(801, 805), ":partly_sunny:"),
]


def get_weather_emoji(weather_id: int) -> str:
    for code_range, emoji in WEATHER_EMOJI_MAP:
        if weather_id in code_range:
            return emoji
    return ":white_sun_cloud:"


def format_weather_fields(weather: dict) -> list[dict]:
    emoji = get_weather_emoji(weather["weather_id"])
    return [
        {"type": "mrkdwn", "text": f"*날씨*\n{emoji} {weather['description']}"},
        {"type": "mrkdwn", "text": f"*기온*\n{weather['temp']}°C (체감 {weather['feels_like']}°C)"},
        {"type": "mrkdwn", "text": f"*강수 확률*\n{weather['rain_prob']}%"},
        {"type": "mrkdwn", "text": f"*습도*\n{weather['humidity']}%"},
    ]
