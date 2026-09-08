# Project: «АРМ Старосты» (Group 240326 «Матинф» БГПУ)

## Architecture
- **Framework & Runtime**: Python 3.11+, FastAPI (ASGI), aiogram 3.x (async Telegram Bot framework), APScheduler 3.x (cron tasks).
- **Persistence**: SQLite 3 with WAL mode (`PRAGMA journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`) via SQLAlchemy 2.0 Async (`aiosqlite`).
- **Authentication & Security**: Telegram Mini App `initData` cryptographic validation using HMAC-SHA256 with key `b"WebAppData"` and bot token. Role-Based Access Control (RBAC: `STUDENT`, `ZAM`, `STAROSTA`).
- **Geolocation Engine**: Spherical Haversine distance verification ($R = 6,371,000$ m) comparing device coordinates to building reference point. Client & server validation ($accuracy \le 50$ m, $d \le 150$ m, timestamp drift $\le 30$ s).
- **Frontend SPA**: Lightweight Telegram Mini App (`webapp/`) using HTML5, CSS3 (Telegram theme variables), Vanilla JavaScript (Telegram WebApp SDK), Geolocation API, responsive mobile chessboard.
- **Reporting Engine**: `openpyxl` generating official BSPU dean's office attendance sheets with automated formulas (`=COUNTIF(...) * 2`, `=SUM(...)`) and strict cell styling.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Onboarding & Whitelist | Whitelist 240326 reservation, Telegram user registration, pending approval state | M2 | SRS §3.1, DB |
| 2 | 1-Click Inline Confirmation | Starosta inline keyboard `[Подтвердить / Отклонить]` with instant status update | M2 | SRS §3.1, Bot |
| 3 | Telegram Menu Button & Launch | `MenuButtonWebApp` setup, inline button launch, Telegram WebApp SDK initialization | M2 | SRS §3.2, Bot |
| 4 | HMAC-SHA256 InitData Auth | Validates `X-Telegram-Init-Data` against bot token, 24h auth_date expiration, constant-time compare | M1 | API §2, Arch |
| 5 | 3-Tier RBAC Engine | Permissions model distinguishing `STUDENT`, `ZAM`, and `STAROSTA` | M1 | SRS §2, API |
| 6 | Schedule Grid & Subgroups | Day of week, ODD/EVEN week parity, subgroup (1, 2, all) filtering | M1 | DB, API §3 |
| 7 | Checkin Window Calculation | Validates check-in time $[-5\text{ min} \dots +15\text{ min}]$ from pair start, countdown remaining | M1 | SRS §3.3, API |
| 8 | Haversine Distance Engine | Spherical math ($R = 6,371,000$ m) calculating meters between GPS coordinates | M1 | SRS §3.3, API |
| 9 | Dual GPS Accuracy Gate | Client & server filtering: sensor accuracy $\le 50$ m, distance $\le 150$ m | M1 | SRS §3.3, API |
| 10 | Anti-Spoofing & Lock Guards | Clock skew check $\le 30$ s, rejection if pair `is_locked` | M1 | API §4, Arch |
| 11 | Interactive Chessboard Grid | Starosta matrix view of students $\times$ pairs with color-coded badges | M3 | SRS §3.4, WebApp |
| 12 | Status Cycle & Excuse Modal | Single-tap cycle switcher + long-press/modal for excuse reason + audit_log | M3 | SRS §3.4, API |
| 13 | Pair Lock Mechanism | Starosta-only action to permanently seal attendance for a class pair | M1 | API §7, SRS |
| 14 | Dean's Office Excel Generator | `openpyxl` template with 2-tier header, `=COUNTIF(...) * 2` and `=SUM(...)` formulas | M4 | SRS §3.5, Reports |
| 15 | Weekly APScheduler Auto Delivery | Saturday 16:00 cron generating weekly report and sending `.xlsx` via bot | M4 | Arch, SRS §3.5 |
| 16 | On-Demand Report Export | `/report` command & `POST /api/v1/reports/export` with Telegram document delivery | M4 | API §9, Bot |
| 17 | Emergency & Info Broadcast | `CRITICAL` (@all + personal DM) and `INFO` (group chat) messaging | M2 | SRS §3.6, API |
| 18 | Healthcheck & Telemetry | Public `GET /api/v1/health` verifying SQLite connection and bot status | M1 | API §1 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M0 | Survey & Architecture | Mining specs, environment audit, workflow mapping | none | DONE |
| M1 | Core Backend & Database | SQLite WAL, SQLAlchemy async models, seed data, HMAC-SHA256, RBAC, Haversine, REST API | M0 | IN_PROGRESS |
| M2 | Telegram Bot & Onboarding | aiogram 3.x, whitelist onboarding, 1-click confirmation, menu button, alerts broadcast | M1 | PLANNED |
| M3 | TMA Frontend SPA | `webapp/` student view (schedule, countdown, geocheckin), starosta view (chessboard, modal) | M1 | PLANNED |
| M4 | Excel Generator & Scheduler | `openpyxl` dean template, automated formulas, APScheduler cron (Sat 16:00), report delivery | M1, M2 | PLANNED |
| M5 | E2E Integration & Coverage Hardening | 100% pass of E2E test suite (Tiers 1-4) + Tier 5 adversarial stress testing | M1, M2, M3, M4 | PLANNED |

## Interface Contracts
### 1. TMA Frontend ↔ FastAPI REST API
- **Transport**: HTTPS / JSON, RFC 7807 problem details for errors.
- **Headers**: `X-Telegram-Init-Data: <raw_querystring>`
- **Endpoints**:
  - `POST /api/v1/auth/telegram` $\rightarrow$ `{ user: {...}, permissions: {...}, current_week: {...} }`
  - `GET /api/v1/schedule/today` $\rightarrow$ `{ date, day_of_week, week_type, pairs: [...] }`
  - `POST /api/v1/attendance/checkin` $\rightarrow$ Body: `{ pair_id, client_lat, client_lon, accuracy, timestamp }` $\rightarrow$ `{ status, distance_meters, checkin_time, message }`
  - `GET /api/v1/attendance/grid/{pair_id}` $\rightarrow$ `{ pair_id, subject, is_locked, summary, students: [...] }`
  - `PATCH /api/v1/attendance/override` $\rightarrow$ Body: `{ pair_id, student_id, new_status, excuse_reason }` $\rightarrow$ `{ success, pair_id, student_id, status }`
  - `POST /api/v1/attendance/lock/{pair_id}` $\rightarrow$ `{ success, pair_id, is_locked, locked_at }`
  - `POST /api/v1/reports/export` $\rightarrow$ Body: `{ date_from, date_to, delivery_method }` $\rightarrow$ `{ file_name, delivered_to_telegram, ... }`
  - `POST /api/v1/alerts/broadcast` $\rightarrow$ Body: `{ type, title, body }` $\rightarrow$ `{ broadcast_id, queued_recipients, status }`

### 2. Telegram Bot ↔ Backend / Database
- **Bot Framework**: `aiogram 3.x` with `Router`, `FSMContext`.
- **Database Sharing**: Shared async engine / session factory `get_session()` with PRAGMA WAL.
- **Onboarding Flow**: `/start` checks `students` table. If unassigned, lists students with `telegram_id IS NULL`. Upon selection, creates pending claim and notifies starosta with callback data `approve:<student_id>:<tg_id>` and `reject:<student_id>:<tg_id>`.
- **Document Delivery**: Bot instance methods `bot.send_document(chat_id, FSInputFile(path))` used by both export endpoint and APScheduler.

### 3. Backend / Scheduler ↔ Excel Generator
- **Signature**: `generate_dean_report(session: AsyncSession, date_from: date, date_to: date, output_path: Path) -> Path`
- **Output**: `.xlsx` workbook formatted strictly according to BSPU Dean's Office standard with dynamic formulas `=COUNTIF(...) * 2` and `=SUM(...)`.

## Code Layout
```
/Users/sergei/Desktop/tg_bot/
├── app/
│   ├── __init__.py
│   ├── config.py             # Settings via pydantic-settings (.env)
│   ├── core/
│   │   ├── __init__.py
│   │   ├── security.py       # HMAC-SHA256 validation & RBAC dependencies
│   │   ├── geo.py            # Haversine calculation & accuracy filters
│   │   └── time_utils.py     # Academic week parity & pair window calculations
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py     # SQLAlchemy async engine & SQLite WAL PRAGMAs
│   │   ├── models.py         # 7 SQLAlchemy mapped models
│   │   └── seed.py           # Whitelist 240326 & schedule seeders
│   ├── api/
│   │   ├── __init__.py
│   │   ├── router.py         # Main API router (/api/v1)
│   │   ├── deps.py           # Dependency injection (session, current_user)
│   │   └── endpoints/
│   │       ├── health.py     # Healthcheck
│   │       ├── auth.py       # Telegram initData auth
│   │       ├── schedule.py   # Schedule queries
│   │       ├── attendance.py # Checkin, grid, override, lock
│   │       ├── alerts.py     # Broadcast messaging
│   │       └── reports.py    # Excel report export
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── bot_instance.py   # aiogram Bot and Dispatcher setup
│   │   ├── handlers/
│   │   │   ├── onboarding.py # Whitelist onboarding & starosta confirmation
│   │   │   ├── commands.py   # /start, /help, /report, /menu
│   │   │   └── alerts.py     # Broadcast handler
│   │   └── keyboards/
│   │       └── inline.py     # Inline keyboards & WebApp buttons
│   ├── reports/
│   │   ├── __init__.py
│   │   └── excel_generator.py # openpyxl BSPU report generator
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── tasks.py          # APScheduler weekly report & maintenance jobs
│   └── main.py               # Combined FastAPI + aiogram lifespan application
├── webapp/
│   ├── index.html            # Single page app
│   ├── css/
│   │   └── style.css         # Telegram theme styles & responsive chessboard
│   └── js/
│       ├── app.js            # Main TMA controller
│       ├── api.js            # Backend API client with initData header
│       ├── geo.js            # HTML5 Geolocation handler
│       └── chessboard.js     # Attendance matrix & modal override
├── tests/
│   ├── conftest.py           # Fixtures, test DB, mock initData generator
│   ├── test_health.py        # Healthcheck tests
│   ├── test_auth.py          # HMAC-SHA256 & RBAC tests
│   ├── test_geo.py           # Haversine & geocheckin tests
│   ├── test_attendance.py    # Grid, override, lock tests
│   ├── test_excel.py         # Excel generation & formula tests
│   ├── test_bot.py           # Bot handlers & onboarding tests
│   └── test_e2e.py           # Full end-to-end integration workflows
├── requirements.txt
├── .env.example
└── README.md
```
