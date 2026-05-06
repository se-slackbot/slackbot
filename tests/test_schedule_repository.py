"""schedule/repository.py 테스트"""
import pytest
import tempfile
import os
import sqlite3
from datetime import date

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from schedule.repository import (
    init_db,
    get_courses_for_date,
    insert_sample_data,
    add_course,
    update_course,
    delete_course,
    DAY_MAP,
)


@pytest.fixture
def db_path():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    init_db(path)
    yield path
    os.unlink(path)


@pytest.fixture
def db_with_data(db_path):
    insert_sample_data(db_path)
    return db_path


class TestInitDb:
    def test_테이블_생성(self, db_path):
        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        assert ("courses",) in tables

    def test_사용자_소유자_컬럼_생성(self, db_path):
        with sqlite3.connect(db_path) as conn:
            columns = [r[1] for r in conn.execute("PRAGMA table_info(courses)").fetchall()]
        assert "slack_user_id" in columns
        assert "memo" in columns

    def test_멱등성_중복_호출_안전(self, db_path):
        init_db(db_path)
        init_db(db_path)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='courses'").fetchone()[0]
        assert count == 1


class TestGetCoursesForDate:
    def test_월요일_강의_2건_반환(self, db_with_data):
        monday = date(2026, 4, 27)  # 월요일
        assert monday.weekday() == 0
        courses = get_courses_for_date(db_with_data, monday)
        assert len(courses) == 2
        assert all(c["day_of_week"] == "Mon" for c in courses)

    def test_화요일_강의_1건_반환(self, db_with_data):
        tuesday = date(2026, 4, 28)  # 화요일
        courses = get_courses_for_date(db_with_data, tuesday)
        assert len(courses) == 1
        assert courses[0]["course_name"] == "알고리즘"

    def test_강의_시작시간_오름차순_정렬(self, db_with_data):
        monday = date(2026, 4, 27)
        courses = get_courses_for_date(db_with_data, monday)
        times = [c["start_time"] for c in courses]
        assert times == sorted(times)

    def test_주말_강의_없음(self, db_with_data):
        saturday = date(2026, 5, 2)  # 토요일
        assert saturday.weekday() == 5
        courses = get_courses_for_date(db_with_data, saturday)
        assert courses == []

    def test_강의_필드_구조_검증(self, db_with_data):
        friday = date(2026, 5, 1)  # 금요일
        courses = get_courses_for_date(db_with_data, friday)
        assert len(courses) == 1
        c = courses[0]
        assert "course_name" in c
        assert "start_time" in c
        assert "end_time" in c
        assert "room" in c
        assert "professor" in c

    def test_빈_DB_빈_리스트_반환(self, db_path):
        monday = date(2026, 4, 27)
        courses = get_courses_for_date(db_path, monday)
        assert courses == []


class TestInsertSampleData:
    def test_샘플_6건_삽입(self, db_path):
        insert_sample_data(db_path)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        assert count == 6

    def test_중복_삽입시_기존_데이터_교체(self, db_path):
        insert_sample_data(db_path)
        insert_sample_data(db_path)
        with sqlite3.connect(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        assert count == 6


class TestUserSchedule:
    def test_사용자별_일정_조회(self, db_path):
        add_course(db_path, "U_A", "자료구조", "Mon", "09:00", "10:00", "101")
        add_course(db_path, "U_B", "컴파일러", "Mon", "11:00", "12:00", "202")

        monday = date(2026, 4, 27)
        courses = get_courses_for_date(db_path, monday, "U_A")

        assert len(courses) == 1
        assert courses[0]["course_name"] == "자료구조"
        assert courses[0]["slack_user_id"] == "U_A"

    def test_사용자_일정이_없으면_기본_일정_폴백(self, db_with_data):
        monday = date(2026, 4, 27)
        courses = get_courses_for_date(db_with_data, monday, "U_EMPTY")
        assert len(courses) == 2
        assert all(c["slack_user_id"] == "default" for c in courses)

    def test_사용자_일정_수정과_삭제(self, db_path):
        course_id = add_course(db_path, "U_A", "자료구조", "Mon", "09:00", "10:00")

        updated = update_course(db_path, "U_A", course_id, room="303", memo="중간고사")
        monday = date(2026, 4, 27)
        courses = get_courses_for_date(db_path, monday, "U_A")

        assert updated is True
        assert courses[0]["room"] == "303"
        assert courses[0]["memo"] == "중간고사"
        assert delete_course(db_path, "U_A", course_id) is True
        assert get_courses_for_date(db_path, monday, "U_A") == []

    def test_다른_사용자_일정은_수정_삭제_불가(self, db_path):
        course_id = add_course(db_path, "U_A", "자료구조", "Mon", "09:00", "10:00")
        assert update_course(db_path, "U_B", course_id, room="999") is False
        assert delete_course(db_path, "U_B", course_id) is False


class TestDayMap:
    def test_요일_매핑_정확성(self):
        assert DAY_MAP[0] == "Mon"
        assert DAY_MAP[1] == "Tue"
        assert DAY_MAP[2] == "Wed"
        assert DAY_MAP[3] == "Thu"
        assert DAY_MAP[4] == "Fri"
        assert DAY_MAP[5] == "Sat"
        assert DAY_MAP[6] == "Sun"
