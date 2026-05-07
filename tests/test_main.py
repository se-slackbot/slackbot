"""main.py 보조 함수 테스트"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from main import _ensure_db_directory


def test_ensure_db_directory_파일명만_있어도_성공():
    _ensure_db_directory("bot.db")


def test_ensure_db_directory_상위_디렉터리_생성():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "nested", "bot.db")
        _ensure_db_directory(db_path)
        assert os.path.isdir(os.path.join(tmp, "nested"))
