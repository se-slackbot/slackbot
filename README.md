# Slack Weather & Schedule Bot

날씨·강의 시간표·Google Calendar 일정을 지정 시각에 Slack으로 보내는 개인 일정 봇입니다. Slack 명령어로 시간표를 관리하고 ICS 캘린더로 구독할 수 있습니다.

## 기술 스택

Python · Slack Bolt · FastAPI · APScheduler · SQLite / PostgreSQL

의존성은 [requirements.txt](requirements.txt)에서 관리합니다.

## 시작하기

### 사전 요구사항

- Python 3.11 이상
- Slack App과 OpenWeatherMap API 키
- [Slack App 설정](https://github.com/SE-SlackBot/.github/blob/main/reference/deploy.md#2-slack-app-설정)에 따른 토큰·권한·명령어 등록

### 설치 및 실행

저장소 루트에서 실행합니다. `.env.example`을 복사한 뒤 [환경 변수 안내](https://github.com/SE-SlackBot/.github/blob/main/reference/deploy.md#환경-변수)의 필수값을 입력한 뒤 실행합니다.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python main.py
```

Windows에서는 가상환경 활성화에 `.venv\Scripts\Activate.ps1`을 사용합니다.

### 환경 변수

필수값과 선택 설정은 [환경 변수 안내](https://github.com/SE-SlackBot/.github/blob/main/reference/deploy.md#환경-변수), 초기 파일은 [.env.example](.env.example)을 참고합니다.

## 사용 방법

### 명령어

| 명령어 | 설명 |
| --- | --- |
| `/weather [도시]` | 현재 날씨와 강수확률 |
| `/schedule [오늘\|내일\|YYYY-MM-DD]` | 날짜별 시간표 |
| `/schedule 추가 <요일> <시작> <종료> <과목> [장소] [교수] [메모]` | 일정 추가 |
| `/schedule 수정 <ID> <field=value>...` | 일정 수정 |
| `/schedule 삭제 <ID>` | 일정 삭제 |
| `/schedule 목록` | 등록한 개인 일정과 ID 조회 |
| `/config [도시] [HH:MM] [timezone]` | 알림 설정 조회·변경 |
| `/brief` | 날씨·시간표·캘린더 즉시 조회 |
| `/bot-help` | 도움말 |

`/날씨`, `/시간표`, `/설정`, `/브리핑`, `/도움말`과 `/날씨1` 같은 숫자 접미 별칭도 지원합니다.

```text
/시간표 추가 월 09:00 10:30 알고리즘 공학관401호 박교수
/시간표 수정 12 room="공학관 301호" start=10:00
/설정 Seoul 07:00 Asia/Seoul
```

### 캘린더 연동

Google Calendar 연결은 [사용자별 OAuth 인증](https://github.com/SE-SlackBot/.github/blob/main/reference/deploy.md#3-google-calendar-선택)을 따릅니다.
시간표를 외부 캘린더에서 구독하려면 ICS API 주소를 등록합니다.

```text
http://localhost:3000/calendar/{slack_user_id}.ics?token={CALENDAR_ACCESS_TOKEN}
```

원격 구독 시 `localhost:3000`을 배포 서버 주소로 바꿉니다. 연결 오류는 [트러블슈팅](https://github.com/SE-SlackBot/.github/blob/main/reference/deploy.md#7-트러블슈팅)을 참고합니다.

## 테스트

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

자동 검증 설정은 [CI 워크플로](.github/workflows/ci.yml)를 참고합니다.

## 관련 문서

| 문서 | 내용 |
| --- | --- |
| [spec.md](https://github.com/SE-SlackBot/.github/blob/main/spec.md) | 요구사항·동작 계약·완료 기준 |
| [plan.md](https://github.com/SE-SlackBot/.github/blob/main/plan.md) | 구현 방향·검증 전략 |
| [tasks.md](https://github.com/SE-SlackBot/.github/blob/main/tasks.md) | 진행 현황·남은 작업 |
| [deploy.md](https://github.com/SE-SlackBot/.github/blob/main/reference/deploy.md) | Slack App·OAuth 설정, 배포·운영·트러블슈팅 |
| [작업 지침](https://github.com/SE-SlackBot/.github/blob/main/AGENTS.md) | 문서별 역할·변경 원칙 |
