"""slack/commands.py 보조 함수 테스트"""
import pytest
from datetime import date
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from slack.commands import _parse_date_arg, _is_valid_time


class TestParseDateArg:
    def test_빈_문자열_오늘_반환(self):
        d, label = _parse_date_arg("")
        assert d == date.today()
        assert label == "오늘"

    def test_오늘_키워드(self):
        d, label = _parse_date_arg("오늘")
        assert d == date.today()
        assert label == "오늘"

    def test_내일_키워드(self):
        d, label = _parse_date_arg("내일")
        from datetime import timedelta
        assert d == date.today() + timedelta(days=1)
        assert label == "내일"

    def test_ISO_날짜_형식(self):
        d, label = _parse_date_arg("2026-05-01")
        assert d == date(2026, 5, 1)
        assert label == "2026-05-01"

    def test_잘못된_형식_오늘_반환(self):
        d, label = _parse_date_arg("모레")
        assert d == date.today()
        assert label == "오늘"

    def test_잘못된_날짜_오늘_반환(self):
        d, label = _parse_date_arg("2026-13-99")
        assert d == date.today()
        assert label == "오늘"


class TestIsValidTime:
    def test_정상_시각(self):
        assert _is_valid_time("07:00") is True
        assert _is_valid_time("00:00") is True
        assert _is_valid_time("23:59") is True

    def test_경계값_시각(self):
        assert _is_valid_time("00:00") is True
        assert _is_valid_time("23:59") is True

    def test_잘못된_시_범위(self):
        assert _is_valid_time("24:00") is False
        assert _is_valid_time("25:30") is False

    def test_잘못된_분_범위(self):
        assert _is_valid_time("07:60") is False
        assert _is_valid_time("12:99") is False

    def test_구분자_없음(self):
        assert _is_valid_time("0700") is False

    def test_빈_문자열(self):
        assert _is_valid_time("") is False

    def test_문자_포함(self):
        assert _is_valid_time("ab:cd") is False

    def test_콜론_초과(self):
        assert _is_valid_time("07:00:00") is False
