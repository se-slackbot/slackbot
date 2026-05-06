# Slack Weather & Schedule Bot

매일 아침 날씨와 강의 시간표를 Slack으로 전달하는 자동화 봇입니다.

## 기능

- **데일리 브리프** — 매일 지정 시각에 날씨 + 강의 일정을 `#daily-brief` 채널에 자동 전송
- **슬래시 커맨드** — `/날씨`, `/시간표`, `/설정`, `/도움말`로 즉시 조회
- **사용자 커스터마이징** — 사용자별 지역, 알림 시각, 타임존, 일정 저장 지원

## 기술 스택

| 구분 | 기술 |
|------|------|
| 런타임 | Python 3.11+ |
| Slack SDK | Slack Bolt for Python |
| 스케줄러 | APScheduler 3.x |
| 날씨 API | OpenWeatherMap (무료 플랜) |
| 데이터 저장 | SQLite |

## 데이터 저장

SQLite DB에는 사용자별로 아래 데이터가 저장됩니다.

| 테이블 | 저장 데이터 |
|--------|-------------|
| `user_config` | Slack 사용자 ID, 도시/지역, 알림 시각, 타임존, 추가 설정 JSON |
| `courses` | Slack 사용자 ID별 일정명, 요일, 시작/종료 시각, 장소, 교수, 메모 |

기존 공용 샘플 시간표는 `slack_user_id = "default"`로 저장되며, 개인 일정이 없는 사용자는 이 기본 시간표를 조회합니다.

## 디렉터리 구조

```
slackbot/
├── main.py              # 앱 진입점
├── scheduler.py         # APScheduler 설정 및 재시도 로직
├── config_store.py      # 사용자 설정 SQLite 저장/조회
├── weather/
│   ├── fetcher.py       # OpenWeatherMap API 호출 + 캐시
│   └── formatter.py     # 날씨 코드 → 이모지, Block Kit 필드 변환
├── schedule/
│   ├── repository.py    # 강의 DB 스키마 및 날짜별 조회
│   └── formatter.py     # 강의 목록 mrkdwn 포맷
├── slack/
│   ├── client.py        # chat.postMessage + Exponential Backoff
│   ├── commands.py      # 슬래시 커맨드 핸들러
│   └── message_builder.py # Block Kit JSON 조합
├── data/                # SQLite DB 저장 위치 (gitignore)
├── .env.example         # 환경 변수 템플릿
└── requirements.txt
```

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 아래 값을 입력합니다.

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `SLACK_BOT_TOKEN` | ✅ | `xoxb-`로 시작하는 Bot Token |
| `SLACK_SIGNING_SECRET` | ✅ | Slack App 서명 검증 시크릿 |
| `OPENWEATHER_API_KEY` | ✅ | OpenWeatherMap API 키 |
| `SLACK_CHANNEL_ID` | ✅ | `#daily-brief` 채널 ID |
| `SLACK_APP_TOKEN` | — | Socket Mode 사용 시 `xapp-` 토큰 |
| `NOTIFY_TIME` | — | 알림 시각 (기본값: `07:00`) |
| `DB_PATH` | — | SQLite 파일 경로 (기본값: `./data/bot.db`) |

### 3. Slack App 설정

1. [api.slack.com/apps](https://api.slack.com/apps) → **Create New App**
2. **OAuth & Permissions** → Bot Token Scopes 추가: `chat:write`, `commands`, `im:write`
3. **Slash Commands** → `/날씨`, `/시간표`, `/설정`, `/도움말` 등록
4. 봇을 `#daily-brief` 채널에 초대: `/invite @봇이름`

> **로컬 개발** 시 [Socket Mode](https://api.slack.com/apis/connections/socket)를 활성화하면 ngrok 없이 실행할 수 있습니다.  
> **App-Level Tokens**에서 `connections:write` 권한으로 토큰을 발급한 뒤 `SLACK_APP_TOKEN`에 입력하세요.

### 4. 실행

```bash
# HTTP 모드 (기본 포트 3000)
python main.py

# Socket Mode (SLACK_APP_TOKEN 설정 시 자동 선택)
python main.py
```

## 슬래시 커맨드

| 커맨드 | 인자 | 동작 |
|--------|------|------|
| `/날씨` | `[도시명]` | 실시간 날씨 조회 (생략 시 설정된 도시) |
| `/시간표` | `[오늘\|내일\|YYYY-MM-DD]` | 해당 날짜 강의 목록 조회 |
| `/설정` | `[도시] [HH:MM]` | 위치 및 알림 시각 변경 |
| `/도움말` | — | 커맨드 목록 안내 |

모든 커맨드 응답은 본인에게만 보이는 ephemeral 메시지입니다.

## 에러 처리

| 상황 | 처리 방법 |
|------|-----------|
| 날씨 API 호출 실패 | 1시간 TTL 캐시 데이터로 폴백 |
| Slack 전송 실패 | Exponential Backoff 재시도 (최대 3회) |
| DB 연결 오류 | 에러 로그 + Slack 알림 채널 통보 |
| API 키 오류 | 즉시 스케줄 중단 |

## 보안

- 토큰 및 API 키는 `.env` 파일로만 관리 — 소스코드 하드코딩 금지
- `data/*.db`와 `.env`는 `.gitignore`에 포함되어 있습니다
- Slack Signing Secret으로 모든 요청 서명 검증
