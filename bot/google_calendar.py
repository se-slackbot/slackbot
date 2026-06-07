from __future__ import annotations
import json
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from bot.database import get_google_token, save_google_token

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_DIR = os.getenv("GOOGLE_TOKEN_DIR", os.path.join(os.path.dirname(__file__), "data", "google_tokens"))

# DATABASE_URL이 있으면 DB 저장, 없으면 파일 저장 (로컬 개발 호환)
_USE_DB_TOKENS = bool(os.getenv("DATABASE_URL"))


def _token_file(user_id: str | None) -> str:
    os.makedirs(TOKEN_DIR, exist_ok=True)
    return os.path.join(TOKEN_DIR, f"token_{user_id}.json" if user_id else "token.json")


def _load_token_json(user_id: str | None) -> str | None:
    """DB 또는 파일에서 토큰 JSON 문자열 로드."""
    if _USE_DB_TOKENS:
        return get_google_token(user_id or "default")
    token_file = _token_file(user_id)
    if not os.path.exists(token_file):
        return None
    with open(token_file) as f:
        return f.read()


def _save_token_json(user_id: str | None, token_json: str) -> None:
    """DB 또는 파일에 토큰 JSON 문자열 저장."""
    if _USE_DB_TOKENS:
        save_google_token(user_id or "default", token_json)
    else:
        with open(_token_file(user_id), "w") as f:
            f.write(token_json)


def _get_credentials(user_id: str | None = None) -> Credentials | None:
    token_json = _load_token_json(user_id)
    if not token_json:
        if os.path.exists(CREDENTIALS_FILE):
            logger.info("Google Calendar 미인증 사용자: %s", user_id)
        else:
            logger.warning("credentials.json 없음 - Google Calendar 연동 비활성화")
        return None

    creds = Credentials.from_authorized_user_info(json.loads(token_json), SCOPES)
    if creds.valid:
        return creds
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token_json(user_id, creds.to_json())
        return creds

    logger.info("Google Calendar 토큰이 유효하지 않음, 재인증 필요: %s", user_id)
    return None


def fetch_today_events(timezone: str = "Asia/Seoul", user_id: str | None = None) -> list[dict]:
    """오늘 Google Calendar 일정 가져오기 (사용자별 토큰 사용)"""
    try:
        creds = _get_credentials(user_id)
        if not creds:
            return []

        now = datetime.now(ZoneInfo(timezone))
        result = (
            build("calendar", "v3", credentials=creds)
            .events()
            .list(
                calendarId="primary",
                timeMin=now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                timeMax=now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat(),
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )

        events = [
            {
                "summary": item.get("summary", "(제목 없음)"),
                "time": _event_time(item["start"]),
                "location": item.get("location", ""),
            }
            for item in result.get("items", [])
        ]
        logger.info("Google Calendar 일정 %d개 가져옴 (user=%s)", len(events), user_id)
        return events

    except Exception as e:
        logger.error("Google Calendar 조회 실패: %s (user=%s)", e, user_id)
        return []


def _event_time(start: dict) -> str:
    """시각이 있으면 HH:MM, 종일 일정이면 '종일'."""
    start_val = start.get("dateTime", start.get("date", ""))
    return datetime.fromisoformat(start_val).strftime("%H:%M") if "T" in start_val else "종일"


def authorize_user(user_id: str) -> bool:
    """사용자 Google Calendar OAuth 인증 — 로컬 실행 시 브라우저 열림, 토큰은 DB/파일에 저장"""
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error("credentials.json 없음")
        return False
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        _save_token_json(user_id, creds.to_json())
        logger.info("Google Calendar 인증 완료: %s (DB=%s)", user_id, _USE_DB_TOKENS)
        return True
    except Exception as e:
        logger.error("Google Calendar 인증 실패: %s", e)
        return False
