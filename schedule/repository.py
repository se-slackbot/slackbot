from __future__ import annotations
import sqlite3
import logging
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"
}
DEFAULT_SCHEDULE_OWNER = "default"

CREATE_COURSES = """
CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slack_user_id TEXT NOT NULL DEFAULT 'default',
    course_name TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    room        TEXT,
    professor   TEXT,
    memo        TEXT,
    created_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_COURSES)
        _ensure_columns(conn)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_courses_user_day_time ON courses (slack_user_id, day_of_week, start_time)"
        )
        conn.commit()
    logger.info("강의 DB 초기화 완료: %s", db_path)


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
        courses = _get_courses_for_owner(db_path, owner, day_str)
        if slack_user_id and not courses:
            return _get_courses_for_owner(db_path, DEFAULT_SCHEDULE_OWNER, day_str)
        return courses
    except sqlite3.Error as e:
        logger.error("DB 조회 실패 (재시도 중): %s", e)
        raise


def insert_sample_data(db_path: str) -> None:
    samples = [
        ("컴퓨터 네트워크", "Mon", "09:00", "10:30", "공학관 301호", "김교수"),
        ("운영체제", "Mon", "13:00", "14:30", "공학관 201호", "이교수"),
        ("알고리즘", "Tue", "10:30", "12:00", "공학관 401호", "박교수"),
        ("데이터베이스", "Wed", "09:00", "10:30", "공학관 301호", "최교수"),
        ("소프트웨어공학", "Thu", "15:00", "16:30", "공학관 101호", "정교수"),
        ("머신러닝", "Fri", "10:00", "11:30", "공학관 502호", "한교수"),
    ]
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM courses WHERE slack_user_id = ?", (DEFAULT_SCHEDULE_OWNER,))
        conn.executemany(
            """
            INSERT INTO courses (slack_user_id, course_name, day_of_week, start_time, end_time, room, professor)
            VALUES (?,?,?,?,?,?,?)
            """,
            [(DEFAULT_SCHEDULE_OWNER, *sample) for sample in samples],
        )
        conn.commit()
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
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO courses (
                slack_user_id, course_name, day_of_week, start_time, end_time, room, professor, memo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (slack_user_id, course_name, day_of_week, start_time, end_time, room, professor, memo),
        )
        conn.commit()
        course_id = cur.lastrowid
    logger.info("사용자 일정 추가: %s course_id=%s", slack_user_id, course_id)
    return int(course_id)


def update_course(db_path: str, slack_user_id: str, course_id: int, **fields: Any) -> bool:
    allowed = {
        "course_name",
        "day_of_week",
        "start_time",
        "end_time",
        "room",
        "professor",
        "memo",
    }
    updates = {key: value for key, value in fields.items() if key in allowed}
    if not updates:
        return False
    if "day_of_week" in updates:
        _validate_day(updates["day_of_week"])

    assignments = ", ".join(f"{key} = ?" for key in updates)
    values = [*updates.values(), slack_user_id, course_id]
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            f"""
            UPDATE courses
               SET {assignments}, updated_at = CURRENT_TIMESTAMP
             WHERE slack_user_id = ? AND id = ?
            """,
            values,
        )
        conn.commit()
        changed = cur.rowcount > 0
    logger.info("사용자 일정 수정: %s course_id=%s changed=%s", slack_user_id, course_id, changed)
    return changed


def delete_course(db_path: str, slack_user_id: str, course_id: int) -> bool:
    with sqlite3.connect(db_path) as conn:
        cur = conn.execute(
            "DELETE FROM courses WHERE slack_user_id = ? AND id = ?",
            (slack_user_id, course_id),
        )
        conn.commit()
        deleted = cur.rowcount > 0
    logger.info("사용자 일정 삭제: %s course_id=%s deleted=%s", slack_user_id, course_id, deleted)
    return deleted


def _get_courses_for_owner(db_path: str, slack_user_id: str, day_of_week: str) -> list[dict]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
              FROM courses
             WHERE slack_user_id = ? AND day_of_week = ?
             ORDER BY start_time, end_time, course_name
            """,
            (slack_user_id, day_of_week),
        ).fetchall()
    return [dict(r) for r in rows]


def _ensure_columns(conn: sqlite3.Connection) -> None:
    columns = {row[1] for row in conn.execute("PRAGMA table_info(courses)").fetchall()}
    migrations = [
        ("slack_user_id", "ALTER TABLE courses ADD COLUMN slack_user_id TEXT NOT NULL DEFAULT 'default'"),
        ("memo", "ALTER TABLE courses ADD COLUMN memo TEXT"),
        ("created_at", "ALTER TABLE courses ADD COLUMN created_at TEXT NOT NULL DEFAULT ''"),
        ("updated_at", "ALTER TABLE courses ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''"),
    ]
    for column, statement in migrations:
        if column not in columns:
            conn.execute(statement)
    conn.execute("UPDATE courses SET created_at = CURRENT_TIMESTAMP WHERE created_at = ''")
    conn.execute("UPDATE courses SET updated_at = CURRENT_TIMESTAMP WHERE updated_at = ''")


def _validate_day(day_of_week: str) -> None:
    if day_of_week not in DAY_MAP.values():
        raise ValueError("day_of_week must be one of Mon, Tue, Wed, Thu, Fri, Sat, Sun")
