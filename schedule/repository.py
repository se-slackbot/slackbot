from __future__ import annotations
import logging
import os
from datetime import date
from typing import Any

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"
}
DEFAULT_SCHEDULE_OWNER = "default"

CREATE_COURSES = """
CREATE TABLE IF NOT EXISTS courses (
    id            SERIAL PRIMARY KEY,
    slack_user_id TEXT NOT NULL DEFAULT 'default',
    course_name   TEXT NOT NULL,
    day_of_week   TEXT NOT NULL,
    start_time    TEXT NOT NULL,
    end_time      TEXT NOT NULL,
    room          TEXT,
    professor     TEXT,
    memo          TEXT,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMP NOT NULL DEFAULT NOW()
)
"""


def _get_conn():
    return psycopg2.connect(os.environ["DATABASE_URL"])


def init_db(db_path: str) -> None:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(CREATE_COURSES)
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_courses_user_day_time "
                    "ON courses (slack_user_id, day_of_week, start_time)"
                )
    finally:
        conn.close()
    logger.info("강의 DB 초기화 완료")


def get_courses_for_date(
    db_path: str,
    target_date: date | None = None,
    slack_user_id: str | None = None,
) -> list[dict]:
    if target_date is None:
        target_date = date.today()
    day_str = DAY_MAP.get(target_date.weekday())
    if day_str is None:
        return []

    try:
        owner = slack_user_id or DEFAULT_SCHEDULE_OWNER
        courses = _get_courses_for_owner(owner, day_str)
        if slack_user_id and not courses:
            return _get_courses_for_owner(DEFAULT_SCHEDULE_OWNER, day_str)
        return courses
    except Exception as e:
        logger.error("DB 조회 실패: %s", e)
        raise


def get_all_courses_for_user(slack_user_id: str) -> list[dict]:
    """캘린더 ICS 생성용: 사용자의 전체 강의 목록 반환"""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM courses
                WHERE slack_user_id = %s
                ORDER BY day_of_week, start_time
                """,
                (slack_user_id,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def insert_sample_data(db_path: str) -> None:
    samples = [
        ("컴퓨터 네트워크", "Mon", "09:00", "10:30", "공학관 301호", "김교수"),
        ("운영체제",       "Mon", "13:00", "14:30", "공학관 201호", "이교수"),
        ("알고리즘",       "Tue", "10:30", "12:00", "공학관 401호", "박교수"),
        ("데이터베이스",   "Wed", "09:00", "10:30", "공학관 301호", "최교수"),
        ("소프트웨어공학", "Thu", "15:00", "16:30", "공학관 101호", "정교수"),
        ("머신러닝",       "Fri", "10:00", "11:30", "공학관 502호", "한교수"),
    ]
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM courses WHERE slack_user_id = %s",
                    (DEFAULT_SCHEDULE_OWNER,),
                )
                cur.executemany(
                    """
                    INSERT INTO courses
                        (slack_user_id, course_name, day_of_week, start_time, end_time, room, professor)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    [(DEFAULT_SCHEDULE_OWNER, *s) for s in samples],
                )
    finally:
        conn.close()
    logger.info("샘플 강의 데이터 삽입 완료")


def add_course(
    db_path: str,
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
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO courses
                        (slack_user_id, course_name, day_of_week, start_time, end_time, room, professor, memo)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (slack_user_id, course_name, day_of_week, start_time, end_time, room, professor, memo),
                )
                course_id = cur.fetchone()[0]
    finally:
        conn.close()
    logger.info("사용자 일정 추가: %s course_id=%s", slack_user_id, course_id)
    return int(course_id)


def update_course(db_path: str, slack_user_id: str, course_id: int, **fields: Any) -> bool:
    allowed = {"course_name", "day_of_week", "start_time", "end_time", "room", "professor", "memo"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    if "day_of_week" in updates:
        _validate_day(updates["day_of_week"])

    assignments = ", ".join(f"{k} = %s" for k in updates)
    values = [*updates.values(), slack_user_id, course_id]
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE courses
                       SET {assignments}, updated_at = NOW()
                     WHERE slack_user_id = %s AND id = %s
                    """,
                    values,
                )
                changed = cur.rowcount > 0
    finally:
        conn.close()
    logger.info("사용자 일정 수정: %s course_id=%s changed=%s", slack_user_id, course_id, changed)
    return changed


def delete_course(db_path: str, slack_user_id: str, course_id: int) -> bool:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM courses WHERE slack_user_id = %s AND id = %s",
                    (slack_user_id, course_id),
                )
                deleted = cur.rowcount > 0
    finally:
        conn.close()
    logger.info("사용자 일정 삭제: %s course_id=%s deleted=%s", slack_user_id, course_id, deleted)
    return deleted


def _get_courses_for_owner(slack_user_id: str, day_of_week: str) -> list[dict]:
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT * FROM courses
                WHERE slack_user_id = %s AND day_of_week = %s
                ORDER BY start_time, end_time, course_name
                """,
                (slack_user_id, day_of_week),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def _validate_day(day_of_week: str) -> None:
    if day_of_week not in DAY_MAP.values():
        raise ValueError("day_of_week must be one of Mon, Tue, Wed, Thu, Fri, Sat, Sun")
