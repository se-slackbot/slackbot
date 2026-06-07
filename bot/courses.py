from __future__ import annotations
import logging
from datetime import date
from typing import Any

from bot.database import db, is_postgres, placeholder

logger = logging.getLogger(__name__)

DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DEFAULT_SCHEDULE_OWNER = "default"
COURSE_FIELDS = ("course_name", "day_of_week", "start_time", "end_time", "room", "professor", "memo")


def init_db(db_path: str | None = None) -> None:
    pk = "SERIAL PRIMARY KEY" if is_postgres(db_path) else "INTEGER PRIMARY KEY AUTOINCREMENT"
    with db(db_path) as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS courses (
                id            {pk},
                slack_user_id TEXT NOT NULL DEFAULT 'default',
                course_name   TEXT NOT NULL,
                day_of_week   TEXT NOT NULL,
                start_time    TEXT NOT NULL,
                end_time      TEXT NOT NULL,
                room          TEXT,
                professor     TEXT,
                memo          TEXT,
                created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS idx_courses_user_day_time "
            "ON courses (slack_user_id, day_of_week, start_time)"
        )
    logger.info("강의 DB 초기화 완료")


def get_courses_for_date(
    db_path: str | None = None,
    target_date: date | None = None,
    slack_user_id: str | None = None,
) -> list[dict]:
    day = DAYS[(target_date or date.today()).weekday()]
    courses = _courses_of(db_path, slack_user_id or DEFAULT_SCHEDULE_OWNER, day)
    if slack_user_id and not courses:
        return _courses_of(db_path, DEFAULT_SCHEDULE_OWNER, day)
    return courses


def get_all_courses_for_user(slack_user_id: str, db_path: str | None = None) -> list[dict]:
    """사용자의 전체 강의 목록을 월~일 순으로 반환한다(목록 조회·ICS 공용)."""
    with db(db_path, dict_rows=True) as cur:
        cur.execute(
            f"SELECT * FROM courses WHERE slack_user_id = {placeholder(db_path)} "
            "ORDER BY start_time",
            (slack_user_id,),
        )
        rows = [dict(r) for r in cur.fetchall()]
    return sorted(rows, key=lambda c: DAYS.index(c["day_of_week"]) if c["day_of_week"] in DAYS else len(DAYS))


def insert_sample_data(db_path: str | None = None) -> None:
    samples = [
        ("컴퓨터 네트워크", "Mon", "09:00", "10:30", "공학관 301호", "김교수"),
        ("운영체제",       "Mon", "13:00", "14:30", "공학관 201호", "이교수"),
        ("알고리즘",       "Tue", "10:30", "12:00", "공학관 401호", "박교수"),
        ("데이터베이스",   "Wed", "09:00", "10:30", "공학관 301호", "최교수"),
        ("소프트웨어공학", "Thu", "15:00", "16:30", "공학관 101호", "정교수"),
        ("머신러닝",       "Fri", "10:00", "11:30", "공학관 502호", "한교수"),
    ]
    ph = placeholder(db_path)
    with db(db_path) as cur:
        cur.execute(f"DELETE FROM courses WHERE slack_user_id = {ph}", (DEFAULT_SCHEDULE_OWNER,))
        cur.executemany(
            "INSERT INTO courses "
            "(slack_user_id, course_name, day_of_week, start_time, end_time, room, professor) "
            f"VALUES ({', '.join([ph] * 7)})",
            [(DEFAULT_SCHEDULE_OWNER, *s) for s in samples],
        )
    logger.info("샘플 강의 데이터 삽입 완료")


def add_course(
    db_path: str | None,
    slack_user_id: str,
    course_name: str,
    day_of_week: str,
    start_time: str,
    end_time: str,
    room: str | None = None,
    professor: str | None = None,
    memo: str | None = None,
) -> int:
    _validate_day(day_of_week)
    ph = placeholder(db_path)
    postgres = is_postgres(db_path)
    with db(db_path) as cur:
        cur.execute(
            f"INSERT INTO courses (slack_user_id, {', '.join(COURSE_FIELDS)}) "
            f"VALUES ({', '.join([ph] * 8)})" + (" RETURNING id" if postgres else ""),
            (slack_user_id, course_name, day_of_week, start_time, end_time, room, professor, memo),
        )
        course_id = cur.fetchone()[0] if postgres else cur.lastrowid
    logger.info("사용자 일정 추가: %s course_id=%s", slack_user_id, course_id)
    return int(course_id)


def update_course(db_path: str | None, slack_user_id: str, course_id: int, **fields: Any) -> bool:
    updates = {k: v for k, v in fields.items() if k in COURSE_FIELDS}
    if not updates:
        return False
    if "day_of_week" in updates:
        _validate_day(updates["day_of_week"])

    ph = placeholder(db_path)
    assignments = ", ".join(f"{k} = {ph}" for k in updates)
    with db(db_path) as cur:
        cur.execute(
            f"UPDATE courses SET {assignments}, updated_at = CURRENT_TIMESTAMP "
            f"WHERE slack_user_id = {ph} AND id = {ph}",
            [*updates.values(), slack_user_id, course_id],
        )
        changed = cur.rowcount > 0
    logger.info("사용자 일정 수정: %s course_id=%s changed=%s", slack_user_id, course_id, changed)
    return changed


def delete_course(db_path: str | None, slack_user_id: str, course_id: int) -> bool:
    ph = placeholder(db_path)
    with db(db_path) as cur:
        cur.execute(
            f"DELETE FROM courses WHERE slack_user_id = {ph} AND id = {ph}",
            (slack_user_id, course_id),
        )
        deleted = cur.rowcount > 0
    logger.info("사용자 일정 삭제: %s course_id=%s deleted=%s", slack_user_id, course_id, deleted)
    return deleted


def count_courses(db_path: str | None = None) -> int:
    with db(db_path) as cur:
        cur.execute("SELECT COUNT(*) FROM courses")
        return int(cur.fetchone()[0])


def _courses_of(db_path: str | None, slack_user_id: str, day_of_week: str) -> list[dict]:
    ph = placeholder(db_path)
    with db(db_path, dict_rows=True) as cur:
        cur.execute(
            f"SELECT * FROM courses WHERE slack_user_id = {ph} AND day_of_week = {ph} "
            "ORDER BY start_time, end_time, course_name",
            (slack_user_id, day_of_week),
        )
        return [dict(r) for r in cur.fetchall()]


def _validate_day(day_of_week: str) -> None:
    if day_of_week not in DAYS:
        raise ValueError(f"day_of_week must be one of {', '.join(DAYS)}")
