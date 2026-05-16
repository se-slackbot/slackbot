# Slack Weather & Schedule Bot

![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Slack](https://img.shields.io/badge/Slack-Bolt%20for%20Python-4A154B?style=for-the-badge&logo=slack&logoColor=white)
![APScheduler](https://img.shields.io/badge/APScheduler-3.x-2E7D32?style=for-the-badge)
![SQLite](https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![OpenWeatherMap](https://img.shields.io/badge/OpenWeatherMap-API-EB6E4B?style=for-the-badge)
![pytest](https://img.shields.io/badge/pytest-8.x-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white)

매일 아침 날씨와 강의 시간표를 Slack으로 전달하고, 슬래시 커맨드로 개인 일정과 알림 설정을 관리할 수 있는 자동화 봇입니다.

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 프로젝트명 | Slack Weather & Schedule Bot |
| 목적 | Slack 안에서 날씨, 강의 일정, 개인 알림 설정을 한 번에 관리 |
| 주요 사용자 | 수업 일정을 Slack에서 확인하려는 학생 또는 팀 구성원 |
| 실행 방식 | Slack Bolt HTTP 모드 또는 Socket Mode |
| 데이터 저장 | SQLite |
| 외부 API | OpenWeatherMap Current Weather / Forecast API |

## 핵심 목표

- 매일 지정 시각에 날씨와 오늘 강의 일정을 Slack 채널 또는 DM으로 전송합니다.
- `/weather`, `/schedule`, `/config` 등 슬래시 커맨드로 즉시 조회와 설정 변경을 지원합니다.
- 사용자별 도시, 알림 시각, 타임존, 개인 시간표를 SQLite에 저장합니다.
- 날씨 API 실패 시 캐시 데이터로 폴백하고, Slack 전송 실패 시 재시도합니다.
- 주요 로직을 모듈 단위로 분리해 테스트 가능한 구조로 유지합니다.

## 주요 기능

| 기능 | 설명 |
|------|------|
| 데일리 브리프 | 매일 지정 시각에 날씨와 강의 일정을 Slack 메시지로 자동 전송 |
| 실시간 날씨 조회 | `/weather`, `/날씨` 명령어로 도시별 현재 날씨 조회 |
| 날짜별 시간표 조회 | `/schedule`, `/시간표` 명령어로 오늘, 내일, 특정 날짜 일정 조회 |
| 개인 시간표 관리 | Slack 사용자 ID별 개인 일정 추가, 수정, 삭제 |
| 사용자 설정 관리 | 도시, 알림 시각, 타임존을 사용자별로 저장 |
| 장애 대응 | API 캐시 폴백, Slack 전송 재시도, 운영 오류 알림 |

## 기술 스택

| 구분 | 기술 |
|------|------|
| Language | Python 3.11+ |
| Slack App | Slack Bolt for Python |
| Scheduler | APScheduler 3.x |
| Weather API | OpenWeatherMap |
| Database | SQLite |
| HTTP Client | requests |
| Env Management | python-dotenv |
| Test | pytest, requests-mock |

## 아키텍처

```text
Slack Slash Command / Scheduler
        |
        v
main.py
        |
        +-- slack/commands.py         # 슬래시 커맨드 라우팅 및 인자 파싱
        +-- slack/message_builder.py  # Slack Block Kit 메시지 생성
        +-- slack/client.py           # Slack 메시지 전송 및 재시도
        +-- weather/fetcher.py        # OpenWeatherMap API 호출 및 캐시
        +-- weather/formatter.py      # 날씨 데이터 표시 형식 변환
        +-- schedule/repository.py    # 강의 일정 SQLite 저장소
        +-- schedule/formatter.py     # 일정 목록 메시지 포맷
        +-- config_store.py           # 사용자 설정 저장소
        +-- scheduler.py              # 데일리 브리프 스케줄링
```

## 디렉터리 구조

```text
slackbot/
├── main.py
├── scheduler.py
├── config_store.py
├── weather/
│   ├── fetcher.py
│   └── formatter.py
├── schedule/
│   ├── repository.py
│   └── formatter.py
├── slack/
│   ├── client.py
│   ├── commands.py
│   └── message_builder.py
├── tests/
├── data/
├── .env.example
├── requirements.txt
├── requirements-dev.txt
└── DESIGN_SPEC.md
```

## 설치 및 실행

### 1. 저장소 준비

```bash
git clone <repository-url>
cd slackbot
```

### 2. 의존성 설치

```bash
pip install -r requirements.txt
```

개발 및 테스트 의존성이 필요하면 아래 명령어를 추가로 실행합니다.

```bash
pip install -r requirements-dev.txt
```

### 3. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 아래 값을 입력합니다.

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `SLACK_BOT_TOKEN` | 필수 | `xoxb-`로 시작하는 Bot Token |
| `SLACK_SIGNING_SECRET` | 필수 | Slack App 요청 서명 검증 시크릿 |
| `OPENWEATHER_API_KEY` | 필수 | OpenWeatherMap API 키 |
| `SLACK_CHANNEL_ID` | 필수 | 데일리 브리프를 받을 Slack 채널 ID |
| `SLACK_APP_TOKEN` | 선택 | Socket Mode 사용 시 필요한 `xapp-` 토큰 |
| `NOTIFY_TIME` | 선택 | 기본 알림 시각, 기본값 `07:00` |
| `DB_PATH` | 선택 | SQLite 파일 경로, 기본값 `./data/bot.db` |

### 4. Slack App 설정

1. [Slack API Apps](https://api.slack.com/apps)에서 새 앱을 생성합니다.
2. **OAuth & Permissions**에서 Bot Token Scopes를 추가합니다.
   - `chat:write`
   - `commands`
   - `im:write`
3. **Slash Commands**에서 사용할 명령어를 등록합니다.
   - 권장: `/weather`, `/schedule`, `/config`, `/bot-help`
   - 호환: `/날씨`, `/시간표`, `/설정`, `/도움말`
4. HTTP 모드에서는 Request URL을 `https://{your-domain}/slack/events`로 설정합니다.
5. 로컬 개발에서 Socket Mode를 사용할 경우 `SLACK_APP_TOKEN`을 설정합니다.
6. 봇을 데일리 브리프 채널에 초대합니다.

```text
/invite @봇이름
```

### 5. 앱 실행

```bash
python main.py
```

`SLACK_APP_TOKEN`이 설정되어 있으면 Socket Mode로 실행되고, 없으면 HTTP 모드로 실행됩니다.

## 슬래시 커맨드

| 커맨드 | 인자 | 동작 |
|--------|------|------|
| `/weather`, `/날씨` | `[도시명]` | 실시간 날씨 조회 |
| `/schedule`, `/시간표` | `[오늘\|내일\|YYYY-MM-DD]` | 날짜별 강의 목록 조회 |
| `/schedule 추가`, `/시간표 추가` | `<요일> <시작 HH:MM> <종료 HH:MM> <과목명> [장소] [교수] [메모]` | 개인 시간표 일정 추가 |
| `/schedule 수정`, `/시간표 수정` | `<ID> <field=value>...` | 개인 시간표 일정 수정 |
| `/schedule 삭제`, `/시간표 삭제` | `<ID>` | 개인 시간표 일정 삭제 |
| `/config`, `/설정` | `[도시] [HH:MM] [timezone]` | 위치, 알림 시각, 타임존 조회 또는 변경 |
| `/bot-help`, `/도움말` | 없음 | 커맨드 목록 안내 |

모든 커맨드 응답은 본인에게만 보이는 ephemeral 메시지로 전송됩니다.

### 사용 예시

```bash
/날씨 Seoul
/시간표 오늘
/시간표 추가 월 09:00 10:30 알고리즘 공학관401호 박교수
/시간표 추가 수 13:00 14:30 "데이터베이스 설계" "공학관 301호" 최교수
/시간표 수정 12 room="공학관 301호" start=10:00 end=11:30
/시간표 삭제 12
/설정 Seoul 07:00 Asia/Seoul
```

## 데이터 모델

SQLite DB에는 사용자 설정과 강의 일정이 저장됩니다.

| 테이블 | 저장 데이터 |
|--------|-------------|
| `user_config` | Slack 사용자 ID, 도시, 지역, 알림 시각, 타임존, 추가 설정 JSON |
| `courses` | Slack 사용자 ID별 일정명, 요일, 시작/종료 시각, 장소, 교수, 메모 |

개인 일정이 없는 사용자는 `slack_user_id = "default"`로 저장된 기본 샘플 시간표를 조회합니다.

## 에러 처리

| 상황 | 처리 방법 |
|------|-----------|
| 날씨 API 호출 실패 | 1시간 TTL 캐시 데이터로 폴백 |
| Slack 전송 실패 | Exponential Backoff 재시도, 최대 3회 |
| DB 연결 오류 | 에러 로그 기록 및 Slack 알림 채널 통보 |
| API 키 오류 | 스케줄 실행 중단 |

## 테스트

```bash
pytest
```

테스트는 날씨 포맷터, 설정 저장소, 스케줄러, Slack 커맨드, 메시지 빌더, 일정 저장소 등 핵심 모듈을 대상으로 구성되어 있습니다.

## 보안

- 토큰과 API 키는 `.env` 파일에서만 관리합니다.
- `.env`와 `data/*.db`는 Git에 커밋하지 않습니다.
- Slack Signing Secret으로 모든 Slack 요청 서명을 검증합니다.
- 운영 환경에서는 Slack 토큰과 OpenWeatherMap API 키를 주기적으로 교체합니다.
