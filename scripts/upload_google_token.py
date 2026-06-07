"""
로컬 구글 토큰 파일을 PostgreSQL DB에 업로드하는 스크립트.
사용법: python scripts/upload_google_token.py <slack_user_id>
예시:  python scripts/upload_google_token.py U0AJRQ01WNQ
"""
import sys
import os
import json
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"))

if len(sys.argv) < 2:
    print("사용법: python scripts/upload_google_token.py <slack_user_id>")
    sys.exit(1)

user_id = sys.argv[1]
token_file = os.path.join(ROOT_DIR, "data", "google_tokens", f"token_{user_id}.json")

if not os.path.exists(token_file):
    print(f"토큰 파일 없음: {token_file}")
    sys.exit(1)

with open(token_file) as f:
    token_json = f.read()

# JSON 유효성 확인
try:
    json.loads(token_json)
except json.JSONDecodeError:
    print("토큰 파일이 유효한 JSON이 아님")
    sys.exit(1)

from bot.database import save_google_token
save_google_token(user_id, token_json)
print(f"완료: {user_id} 토큰을 DB에 저장했습니다.")
