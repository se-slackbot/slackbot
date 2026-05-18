from __future__ import annotations
import logging
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
CREDENTIALS_FILE = os.path.join(os.path.dirname(__file__), "credentials.json")
TOKEN_DIR = os.getenv("GOOGLE_TOKEN_DIR", os.path.join(os.path.dirname(__file__), "data", "google_tokens"))


def _token_file(user_id: str | None) -> str:
    os.makedirs(TOKEN_DIR, exist_ok=True)
    if user_id:
        return os.path.join(TOKEN_DIR, f"token_{user_id}.json")
    return os.path.join(TOKEN_DIR, "token.json")


def _get_credentials(user_id: str | None = None) -> Credentials | None:
    token_file = _token_file(user_id)
    creds = None

    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_file, "w") as f:
                f.write(creds.to_json())
        else:
            # 토큰 없음 → 해당 사용자는 미인증 상태
            if not os.path.exists(CREDENTIALS_FILE):
                logger.warning("credentials.json 없음 - Google Calendar 연동 비활성화")
            else:
                logger.info("Google Calendar 미인증 사용자: %s", user_id)
            return None

    return creds


def fetch_today_events(timezone: str = "Asia/Seoul", user_id: str | None = None) -> list[dict]:
    """오늘 Google Calendar 일정 가져오기 (사용자별 토큰 사용)"""
    try:
        creds = _get_credentials(user_id)
        if not creds:
            return []

        service = build("calendar", "v3", credentials=creds)
        tz = ZoneInfo(timezone)
        now = datetime.now(tz)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now.replace(hour=23, minute=59, second=59, microsecond=0)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = []
        for item in events_result.get("items", []):
            start_val = item["start"].get("dateTime", item["start"].get("date", ""))

            if "T" in start_val:
                dt = datetime.fromisoformat(start_val)
                time_str = dt.strftime("%H:%M")
            else:
                time_str = "종일"

            events.append({
                "summary": item.get("summary", "(제목 없음)"),
                "time": time_str,
                "location": item.get("location", ""),
            })

        logger.info("Google Calendar 일정 %d개 가져옴 (user=%s)", len(events), user_id)
        return events

    except Exception as e:
        logger.error("Google Calendar 조회 실패: %s (user=%s)", e, user_id)
        return []


def authorize_user(user_id: str) -> bool:
    """사용자 Google Calendar OAuth 인증 — 터미널에서 실행 시 브라우저 열림"""
    if not os.path.exists(CREDENTIALS_FILE):
        logger.error("credentials.json 없음")
        return False
    try:
        flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
        creds = flow.run_local_server(port=0)
        token_file = _token_file(user_id)
        with open(token_file, "w") as f:
            f.write(creds.to_json())
        logger.info("Google Calendar 인증 완료: %s → %s", user_id, token_file)
        return True
    except Exception as e:
        logger.error("Google Calendar 인증 실패: %s", e)
        return False
