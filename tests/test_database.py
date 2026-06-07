"""bot/database.py 보조 함수 테스트"""
import os
import tempfile


from bot.database import ensure_sqlite_directory


def test_ensure_sqlite_directory_파일명만_있어도_성공():
    ensure_sqlite_directory("bot.db")


def test_ensure_sqlite_directory_상위_디렉터리_생성():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "nested", "bot.db")
        ensure_sqlite_directory(db_path)
        assert os.path.isdir(os.path.join(tmp, "nested"))
