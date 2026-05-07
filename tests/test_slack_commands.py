"""slack/commands.py 보조 함수 테스트"""
import pytest
import tempfile
from datetime import date
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from config_store import ConfigStore
from schedule.repository import get_courses_for_date, init_db
from slack.commands import (
    _parse_add_course_arg,
    _parse_date_arg,
    _is_valid_time,
    _normalize_day,
    register_commands,
)


class FakeApp:
    def __init__(self):
        self.handlers = {}

    def command(self, name):
        def decorator(func):
            self.handlers[name] = func
            return func

        return decorator


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    os.unlink(path)


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


class TestNormalizeDay:
    def test_한국어_요일(self):
        assert _normalize_day("월") == "Mon"
        assert _normalize_day("화요일") == "Tue"

    def test_영문_요일(self):
        assert _normalize_day("wed") == "Wed"
        assert _normalize_day("Friday") == "Fri"

    def test_잘못된_요일(self):
        with pytest.raises(ValueError):
            _normalize_day("평일")


class TestParseAddCourseArg:
    def test_필수값_파싱(self):
        parsed = _parse_add_course_arg("추가 월 09:00 10:30 알고리즘")
        assert parsed == {
            "day_of_week": "Mon",
            "start_time": "09:00",
            "end_time": "10:30",
            "course_name": "알고리즘",
            "room": None,
            "professor": None,
            "memo": None,
        }

    def test_선택값_파싱(self):
        parsed = _parse_add_course_arg("추가 수 13:00 14:30 데이터베이스 공학관301호 최교수 팀플")
        assert parsed["day_of_week"] == "Wed"
        assert parsed["room"] == "공학관301호"
        assert parsed["professor"] == "최교수"
        assert parsed["memo"] == "팀플"

    def test_따옴표_포함_파싱(self):
        parsed = _parse_add_course_arg('추가 수 13:00 14:30 "데이터베이스 설계" "공학관 301호" 최교수')
        assert parsed["course_name"] == "데이터베이스 설계"
        assert parsed["room"] == "공학관 301호"

    def test_종료_시각이_시작보다_빠르면_실패(self):
        with pytest.raises(ValueError):
            _parse_add_course_arg("추가 월 10:30 09:00 알고리즘")

    def test_사용법_누락_실패(self):
        with pytest.raises(ValueError):
            _parse_add_course_arg("추가 월 09:00")


class TestRegisterCommandsScheduleAdd:
    def test_영문_alias_명령어도_등록됨(self, db_path):
        app = FakeApp()
        store = ConfigStore(db_path)
        register_commands(app, store, "api-key", db_path)

        for command_name in ["/weather", "/schedule", "/config", "/bot-help"]:
            assert command_name in app.handlers

    def test_시간표_추가_명령어가_사용자_DB에_저장(self, db_path):
        app = FakeApp()
        store = ConfigStore(db_path)
        register_commands(app, store, "api-key", db_path)
        responses = []
        acked = []

        app.handlers["/시간표"](
            ack=lambda: acked.append(True),
            respond=lambda **kwargs: responses.append(kwargs),
            command={
                "user_id": "U_001",
                "text": "추가 월 09:00 10:30 알고리즘 공학관401호 박교수",
            },
        )

        monday = date(2026, 4, 27)
        courses = get_courses_for_date(db_path, monday, "U_001")
        assert acked == [True]
        assert responses[0]["response_type"] == "ephemeral"
        assert "시간표에 추가했습니다" in responses[0]["text"]
        assert len(courses) == 1
        assert courses[0]["course_name"] == "알고리즘"
        assert courses[0]["room"] == "공학관401호"
        assert courses[0]["professor"] == "박교수"


class TestRegisterCommandsConfig:
    def test_설정_명령어_인자_없으면_현재_설정_응답(self, db_path):
        app = FakeApp()
        store = ConfigStore(db_path)
        store.set("U_001", city="Busan", notify_time="08:30")
        register_commands(app, store, "api-key", db_path)
        responses = []
        acked = []

        app.handlers["/config"](
            ack=lambda: acked.append(True),
            respond=lambda **kwargs: responses.append(kwargs),
            say=lambda **kwargs: None,
            command={"user_id": "U_001", "command": "/config", "text": ""},
        )

        assert acked == [True]
        assert responses[0]["response_type"] == "ephemeral"
        assert "현재 설정" in responses[0]["text"]
        assert "Busan" in responses[0]["text"]
