# Slack Weather & Schedule Bot Design Spec

## 1. Overview

Slack Weather & Schedule Bot은 매일 지정된 시각에 날씨와 강의 일정을 Slack으로 전달하고, 사용자가 슬래시 커맨드로 즉시 날씨/시간표/설정을 조회하거나 변경할 수 있는 자동화 봇이다.

이 문서는 현재 프로젝트의 구현 기준 디자인 스펙을 정리하며, 향후 구현이 필요한 확장 지점도 함께 명시한다.

### 1.1 Document Metadata

| Field | Value |
|---|---|
| Version | v1.0 |
| Original Draft Date | 2026-04-27 |
| Current Revision Date | 2026-05-11 |
| Status | Draft |
| Owner | 개발팀 |

## 2. Goals

- 매일 아침 지정된 Slack 채널 또는 사용자 DM으로 데일리 브리프를 전송한다.
- 사용자가 Slack 슬래시 커맨드로 현재 날씨와 날짜별 시간표를 조회할 수 있다.
- 사용자별 도시, 알림 시각, 타임존, 개인 시간표를 SQLite에 저장한다.
- 외부 API 또는 Slack 전송 실패 시 재시도와 캐시 폴백으로 장애 영향을 줄인다.
- 모든 핵심 로직은 단위 테스트 가능한 순수 함수 또는 얇은 서비스 계층으로 분리한다.

## 3. Non-Goals

- 복잡한 캘린더 동기화, 반복 일정 규칙, 휴강/보강 자동 계산은 현재 범위에 포함하지 않는다.
- Slack 인터랙티브 모달, 버튼 기반 설정 UI는 현재 범위에 포함하지 않는다.
- 다중 워크스페이스 OAuth 설치 플로우는 현재 범위에 포함하지 않는다.
- 날씨 예보 전체 타임라인 제공은 현재 범위에 포함하지 않는다.

## 4. Users

### Primary User

수업 일정을 Slack에서 관리하고, 매일 아침 날씨와 오늘 강의를 한 번에 확인하려는 학생 또는 팀 구성원.

### Admin / Operator

Slack App 토큰, OpenWeatherMap API 키, 기본 채널, DB 경로를 설정하고 봇 프로세스를 운영하는 사용자.

## 5. User Flows

### 5.1 Daily Brief

1. APScheduler가 지정 시각에 작업을 실행한다.
2. 봇이 OpenWeatherMap에서 현재 날씨를 조회한다.
3. 봇이 SQLite에서 해당 날짜의 강의 목록을 조회한다.
4. Block Kit 메시지를 생성한다.
5. Slack 채널 또는 사용자 DM으로 메시지를 전송한다.
6. Slack 전송 실패 시 exponential backoff로 최대 3회 재시도한다.

### 5.2 Weather Command

1. 사용자가 `/weather [도시명]` 또는 `/날씨 [도시명]`을 입력한다.
2. 도시명이 있으면 해당 도시를 사용한다.
3. 도시명이 없으면 사용자 설정의 기본 도시를 사용한다.
4. 날씨 정보를 조회하고 ephemeral 메시지로 응답한다.

### 5.3 Schedule Command

1. 사용자가 `/schedule [오늘|내일|YYYY-MM-DD]` 또는 `/시간표 [오늘|내일|YYYY-MM-DD]`를 입력한다.
2. 날짜 인자가 없거나 잘못된 경우 오늘 날짜를 사용한다.
3. 사용자 개인 일정이 있으면 개인 일정을 보여준다.
4. 사용자 개인 일정이 없으면 `default` 소유자의 샘플 일정을 보여준다.
5. 결과를 ephemeral 메시지로 응답한다.

### 5.4 Add Schedule Command

1. 사용자가 `/schedule 추가 <요일> <시작> <종료> <과목명> [장소] [교수] [메모]`를 입력한다.
2. 요일, 시간 형식, 시작/종료 순서를 검증한다.
3. SQLite `courses` 테이블에 사용자 소유 일정으로 저장한다.
4. 생성된 일정 ID를 ephemeral 메시지로 안내한다.

### 5.5 Config Command

1. 사용자가 `/config` 또는 `/설정`을 인자 없이 입력한다.
2. 현재 도시와 알림 시각을 보여준다.
3. 사용자가 `/config Seoul 07:00` 형식으로 입력하면 설정을 저장한다.

## 6. Slash Command Contract

| Command | Arguments | Response | Current Status |
|---|---|---|---|
| `/weather`, `/날씨` | `[city]` | Current weather blocks | Implemented |
| `/schedule`, `/시간표` | `[오늘|내일|YYYY-MM-DD]` | Schedule blocks | Implemented |
| `/schedule 추가`, `/시간표 추가` | `<day> <start> <end> <name> [room] [professor] [memo]` | Text confirmation | Implemented |
| `/config`, `/설정` | `[city] [HH:MM]` | Current config or confirmation | Implemented |
| `/bot-help`, `/도움말` | none | Help blocks | Implemented |
| `/schedule 수정`, `/시간표 수정` | `<id> <field=value>...` | Text confirmation | Planned |
| `/schedule 삭제`, `/시간표 삭제` | `<id>` | Text confirmation | Planned |
| `/config`, `/설정` | `[city] [HH:MM] [timezone]` | Current config or confirmation | Planned |

All command responses should be ephemeral unless a future flow explicitly requires public posting.

## 7. Architecture

```text
main.py
  -> loads environment variables
  -> initializes SQLite schema and sample data
  -> creates Slack Bolt App
  -> registers slash commands
  -> starts APScheduler
  -> starts HTTP mode or Socket Mode

scheduler.py
  -> defines channel daily brief job
  -> defines per-user daily brief polling job
  -> validates timezone fallback
  -> sends operational error notifications

slack/
  commands.py
    -> slash command handlers and argument parsers
  message_builder.py
    -> Slack Block Kit composition
  client.py
    -> Slack message posting with retry

weather/
  fetcher.py
    -> OpenWeatherMap calls and in-memory TTL cache
  formatter.py
    -> weather code to Slack emoji and field formatting

schedule/
  repository.py
    -> SQLite schema, migrations, CRUD, date lookup
  formatter.py
    -> course list formatting

config_store.py
  -> user configuration schema, migrations, get/set/list API
```

### 7.1 Legacy Spec Alignment Notes

The original design spec described the following intended architecture details. Current implementation status is noted where it differs:

| Legacy Spec Item | Current Design Position |
|---|---|
| Weather API and schedule DB query run in parallel | Planned optimization. Current scheduler performs these steps sequentially. |
| Data storage supports SQLite / CSV | SQLite is the supported implementation. CSV is out of current scope unless reintroduced explicitly. |
| `SlackClient` handles both `chat.postMessage` and slash commands | Split by responsibility: `slack/client.py` posts messages; `slack/commands.py` handles slash commands. |
| Courses are weekday-only `Mon` to `Fri` | Current implementation supports `Mon` through `Sun`. |
| Scheduler failure retry logic | Slack posting retries are implemented in `slack/client.py`; scheduler-level DB/weather retries are planned. |

## 8. Data Model

### 8.1 `user_config`

| Column | Type | Required | Description |
|---|---|---:|---|
| `slack_user_id` | TEXT | Yes | Slack user ID, primary key |
| `city` | TEXT | Yes | OpenWeatherMap city query |
| `region` | TEXT | Yes | Human-readable region, currently aligned with city |
| `notify_time` | TEXT | Yes | Daily notification time in `HH:MM` format |
| `timezone` | TEXT | Yes | IANA timezone, default `Asia/Seoul` |
| `settings_json` | TEXT | Yes | Additional user settings as JSON object |
| `created_at` | TEXT | Yes | Creation timestamp |
| `updated_at` | TEXT | Yes | Update timestamp |

### 8.2 `courses`

| Column | Type | Required | Description |
|---|---|---:|---|
| `id` | INTEGER | Yes | Auto-increment primary key |
| `slack_user_id` | TEXT | Yes | Owner user ID, or `default` for sample schedule |
| `course_name` | TEXT | Yes | Course or event name |
| `day_of_week` | TEXT | Yes | One of `Mon`, `Tue`, `Wed`, `Thu`, `Fri`, `Sat`, `Sun` |
| `start_time` | TEXT | Yes | Start time in `HH:MM` format |
| `end_time` | TEXT | Yes | End time in `HH:MM` format |
| `room` | TEXT | No | Location |
| `professor` | TEXT | No | Instructor |
| `memo` | TEXT | No | Free-form note |
| `created_at` | TEXT | Yes | Creation timestamp |
| `updated_at` | TEXT | Yes | Update timestamp |

## 9. Scheduling Design

### 9.1 Channel Brief

- Uses `NOTIFY_TIME` from environment.
- Uses the default timezone `Asia/Seoul`.
- Posts to `SLACK_CHANNEL_ID`.
- Uses the configured default city from `DEFAULT_CITY`, falling back to `Seoul`.

### 9.2 Per-User Brief

- Runs once per minute.
- Reads all saved user configs.
- Compares each user's configured `notify_time` against the current time in that user's timezone.
- Sends the brief by DM using the Slack user ID as the channel.
- Deduplicates sends with an in-memory key of `(user_id, date, notify_time)`.

## 10. Weather Design

### 10.1 Current Weather

- API: OpenWeatherMap `/data/2.5/weather`
- Units: metric
- Language: Korean
- Result fields:
  - city
  - temperature
  - feels-like temperature
  - humidity
  - weather ID
  - description
  - rain probability

### 10.2 Rain Probability

- API: OpenWeatherMap `/data/2.5/forecast`
- Uses the first forecast item only.
- Converts `pop` from `0.0..1.0` to percentage.
- Returns `0` when forecast lookup fails.

### 10.3 Cache

- In-memory cache.
- Key format: `weather:{city}`.
- TTL: 1 hour.
- Valid cached data is used before making a network request.
- If current weather API fails and valid cached data exists, cached data is returned.

## 11. Message Design

### 11.1 Daily Brief Blocks

The daily brief should include:

- Header with weather emoji and date.
- Weather fields:
  - condition
  - temperature
  - rain probability
  - humidity
- Divider.
- Today's course list.
- Context footer with update time and app version.

### 11.2 Weather Blocks

The weather command response should include:

- City name.
- Weather emoji and description.
- Temperature and feels-like temperature.
- Rain probability.
- Humidity.

### 11.3 Schedule Blocks

The schedule command response should include:

- Date label.
- Ordered list of courses by start time.
- Empty-state message when no courses exist.

## 12. Error Handling

| Scenario | Expected Behavior |
|---|---|
| Missing required env var | Log error and exit process |
| Weather API failure with valid cache | Use cached weather |
| Weather API failure without cache | Surface warning to command user or skip scheduled brief |
| Forecast API failure | Use rain probability `0` |
| Slack post failure | Retry up to 3 times with exponential backoff |
| DB lookup failure in scheduler | Notify operational Slack channel/user and skip job |
| Invalid command argument | Return ephemeral warning with expected format |
| Invalid timezone | Fall back to `Asia/Seoul` and log warning |

### 12.1 Error Scenario Matrix

| Scenario | Handling | Notification |
|---|---|---|
| Weather API call failure | Use valid cached weather data when available; otherwise skip scheduled brief or warn command user | Slack operational channel/user when scheduled |
| DB connection or query failure | Skip the affected job after logging the failure | Console log and Slack operational notification |
| Slack message delivery failure | Retry with exponential backoff up to 3 attempts | Log final failure |
| API key expired or invalid | Planned: detect authentication errors and stop or disable scheduled jobs | Planned: admin DM or operational alert |
| Forecast API failure | Continue with `rain_prob = 0` | Debug or warning log only |

### 12.2 Logging Levels

| Level | Usage |
|---|---|
| `DEBUG` | Raw or detailed API response data useful during development |
| `INFO` | Scheduler start, job execution, successful Slack sends, DB initialization |
| `WARNING` | Retryable failures, cache usage, invalid timezone fallback |
| `ERROR` | Final Slack delivery failure, DB errors, weather fetch failures without usable fallback |

## 13. Validation Rules

- Time values must use `HH:MM`.
- Hour must be `0..23`.
- Minute must be `0..59`.
- Course end time must be later than start time.
- Day aliases should support Korean and English:
  - `월`, `월요일`, `mon`, `monday` -> `Mon`
  - `화`, `화요일`, `tue`, `tuesday` -> `Tue`
  - `수`, `수요일`, `wed`, `wednesday` -> `Wed`
  - `목`, `목요일`, `thu`, `thursday` -> `Thu`
  - `금`, `금요일`, `fri`, `friday` -> `Fri`
  - `토`, `토요일`, `sat`, `saturday` -> `Sat`
  - `일`, `일요일`, `sun`, `sunday` -> `Sun`
- Quoted arguments should be supported for values containing spaces.

## 14. Environment Variables

| Variable | Required | Default | Description |
|---|---:|---|---|
| `SLACK_BOT_TOKEN` | Yes | none | Slack bot token |
| `SLACK_SIGNING_SECRET` | Yes | none | Slack signing secret |
| `OPENWEATHER_API_KEY` | Yes | none | OpenWeatherMap API key |
| `SLACK_CHANNEL_ID` | Yes | none | Default channel for daily brief |
| `SLACK_APP_TOKEN` | No | empty | Socket Mode token |
| `NOTIFY_TIME` | No | `07:00` | Channel daily brief time |
| `DB_PATH` | No | `./data/bot.db` | SQLite DB path |
| `DEFAULT_CITY` | No | `Seoul` | Default weather city |
| `PORT` | No | `3000` | HTTP mode port |
| `DEBUG` | No | unset | Enables debug logging when set |

## 15. Testing Strategy

### Unit Tests

- Weather formatter emoji mapping and fields.
- Weather fetcher cache behavior and forecast fallback.
- Schedule repository schema initialization, sample data, user fallback, CRUD.
- Config store defaults, persistence, migrations, JSON settings.
- Slack command argument parsing and command handler responses.
- Message builder Block Kit output shape.
- Scheduler due checks and user brief behavior.
- Slack client retry behavior.

### Integration Tests

Recommended future additions:

- End-to-end command handler test with a temporary DB and mocked Slack app.
- Scheduler daily brief test covering weather fetch, schedule lookup, message build, and Slack post.
- Migration test from older DB schemas.

## 16. Security and Privacy

- Secrets must be loaded from environment variables only.
- `.env` and SQLite DB files must not be committed.
- Slack command responses should default to ephemeral to avoid exposing personal schedules.
- Logs should not include tokens, API keys, or full Slack payloads containing sensitive user content.
- User schedule data should be scoped by `slack_user_id`.
- Slack Signing Secret must be used to verify HTTP webhook requests.
- OpenWeatherMap free-plan rate limits should be protected by caching and future request throttling.

## 17. Development Roadmap

This roadmap preserves the original project staging from the earlier design spec while reflecting the current codebase structure.

| Phase | Goal | Key Tasks | Estimate |
|---|---|---|---|
| 1 | Slack app setup | Issue Bot Token, configure OAuth scopes, invite bot to channel | 0.5 day |
| 2 | Weather module | API call, parsing, emoji mapping, unit tests | 1 day |
| 3 | Schedule module | DB schema, sample data, date query logic | 1 day |
| 4 | Message builder | Compose Block Kit JSON and preview/test output | 1 day |
| 5 | Scheduler integration | Configure APScheduler, error handling, retry behavior | 0.5 day |
| 6 | Slash commands | Implement `/weather`, `/schedule`, `/config`, `/bot-help` handlers and aliases | 1 day |
| 7 | Test and deploy | Integration tests, `.env` setup, server or local Socket Mode execution | 1 day |

Total original estimate: 5 to 6 business days for one developer.

## 18. Planned Implementation Items

### P1

- Add `/schedule 수정` and `/schedule 삭제` command handling using existing repository functions.
- Extend `/config` to accept and display timezone.
- Improve command help text so it reflects all supported aliases and planned schedule management commands once implemented.

### P2

- Distinguish OpenWeatherMap authentication errors from transient API errors.
- Stop or disable scheduled jobs when API key configuration is invalid.
- Make weather cache fallback log messages match actual cache behavior.
- Add command support for listing personal course IDs clearly before edit/delete flows.

### P3

- Add optional Slack interactive modals for configuration and schedule editing.
- Add import/export support for course schedules.
- Persist send deduplication state if process restarts become common during notification windows.
- Add explicit OpenWeatherMap rate-limit guardrails beyond the current in-memory cache.
- Add scheduler-level retries for transient DB and weather failures where appropriate.

## 19. Acceptance Criteria

- Required environment variables are validated before the app starts.
- Running the app initializes DB schema and sample schedule when needed.
- Slash commands respond with ephemeral messages.
- Weather command works with explicit city and user default city.
- Schedule command works for today, tomorrow, and ISO date input.
- Add schedule command supports quoted arguments with spaces.
- Daily brief can post a weather and schedule message to Slack.
- User-specific daily brief respects each user's notify time and timezone.
- Test suite passes with `python3 -m pytest -q`.
