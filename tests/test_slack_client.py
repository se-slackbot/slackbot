"""slack/client.py 테스트"""
import pytest
import time
from unittest.mock import MagicMock, patch
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from slack.client import post_daily_brief, _post_with_retry, MAX_RETRIES


SAMPLE_BLOCKS = [{"type": "section", "text": {"type": "mrkdwn", "text": "테스트"}}]


def _make_app(fail_times=0):
    app = MagicMock()
    call_count = {"n": 0}

    def post_message(**kwargs):
        call_count["n"] += 1
        if call_count["n"] <= fail_times:
            raise Exception("슬랙 전송 실패")

    app.client.chat_postMessage.side_effect = post_message
    return app


class TestPostDailyBrief:
    def test_정상_전송_성공(self):
        app = _make_app(fail_times=0)
        post_daily_brief(app, "C_CHANNEL", SAMPLE_BLOCKS)
        app.client.chat_postMessage.assert_called_once()

    def test_채널_및_블록_전달_검증(self):
        app = _make_app(fail_times=0)
        post_daily_brief(app, "C_TEST123", SAMPLE_BLOCKS)
        call_kwargs = app.client.chat_postMessage.call_args[1]
        assert call_kwargs["channel"] == "C_TEST123"
        assert call_kwargs["blocks"] == SAMPLE_BLOCKS


class TestPostWithRetry:
    @patch("slack.client.time.sleep")
    def test_1회_실패_후_성공(self, mock_sleep):
        app = _make_app(fail_times=1)
        _post_with_retry(app, "C_CHANNEL", SAMPLE_BLOCKS)
        assert app.client.chat_postMessage.call_count == 2

    @patch("slack.client.time.sleep")
    def test_최대_재시도_초과시_예외_발생(self, mock_sleep):
        app = _make_app(fail_times=MAX_RETRIES + 1)
        with pytest.raises(Exception):
            _post_with_retry(app, "C_CHANNEL", SAMPLE_BLOCKS)
        assert app.client.chat_postMessage.call_count == MAX_RETRIES

    @patch("slack.client.time.sleep")
    def test_지수_백오프_슬립_호출(self, mock_sleep):
        app = _make_app(fail_times=2)
        _post_with_retry(app, "C_CHANNEL", SAMPLE_BLOCKS)
        assert mock_sleep.call_count == 2
        delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert delays[0] < delays[1]  # 지수 증가 확인
