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
TOKEN_FILE = os.path.join(os.path.dirname(__file__), "token.json")


def _get_credentials() -> Credentials | None:
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                logger.warning("credentials.json 없음 - Google Calendar 연동 비활성화")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return creds


def fetch_today_events(timezone: str = "Asia/Seoul") -> list[dict]:
    """오늘 Google Calendar 일정 가져오기"""
    try:
        creds = _get_credentials()
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
            end_val = item["end"].get("dateTime", item["end"].get("date", ""))

            # 시간 파싱
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

        logger.info("Google Calendar 일정 %d개 가져옴", len(events))
        return events

    except Exception as e:
        logger.error("Google Calendar 조회 실패: %s", e)
        return []
