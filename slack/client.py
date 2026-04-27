import logging
import time

from slack_bolt import App

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0


def post_daily_brief(app: App, channel_id: str, blocks: list[dict]) -> None:
    _post_with_retry(app, channel_id, blocks)


def _post_with_retry(app: App, channel_id: str, blocks: list[dict]) -> None:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            app.client.chat_postMessage(channel=channel_id, blocks=blocks, text="오늘의 날씨 & 강의 일정")
            logger.info("슬랙 메시지 전송 성공 (채널: %s)", channel_id)
            return
        except Exception as e:
            if attempt == MAX_RETRIES:
                logger.error("슬랙 전송 최종 실패: %s", e)
                raise
            delay = BASE_DELAY * (2 ** (attempt - 1))
            logger.warning("슬랙 전송 실패 (재시도 %d/%d, %.1fs 후): %s", attempt, MAX_RETRIES, delay, e)
            time.sleep(delay)
