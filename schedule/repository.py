import sqlite3
import logging
from datetime import date, timedelta

logger = logging.getLogger(__name__)

DAY_MAP = {
    0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"
}

CREATE_COURSES = """
CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT NOT NULL,
    day_of_week TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    room        TEXT,
    professor   TEXT
)
"""


def init_db(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(CREATE_COURSES)
        conn.commit()
    logger.info("강의 DB 초기화 완료: %s", db_path)


def get_courses_for_date(db_path: str, target_date: date | None = None) -> list[dict]:
    if target_date is None:
        target_date = date.today()
    day_str = DAY_MAP.get(target_date.weekday())
    if day_str is None:
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM courses WHERE day_of_week = ? ORDER BY start_time",
                (day_str,),
            ).fetchall()
        return [dict(r) for r in rows]
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
        conn.execute("DELETE FROM courses")
        conn.executemany(
            "INSERT INTO courses (course_name, day_of_week, start_time, end_time, room, professor) VALUES (?,?,?,?,?,?)",
            samples,
        )
        conn.commit()
    logger.info("샘플 강의 데이터 삽입 완료")
