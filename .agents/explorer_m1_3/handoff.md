# Handoff Report — Milestone 1: FastAPI REST API, Pydantic v2 Schemas, RFC 7807 & Lifespan

**Agent:** `explorer_m1_3`  
**To:** Orchestrator (`parent` / `c535a0f4-5f91-43ad-995a-f09dadc735e1`)  
**Date:** 2026-09-08  
**Artifact:** `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_3/m1_api_report.md`  

---

## 1. Observation

1. **Repository Layout & Missing Codebase**:
   - `list_dir` on `/Users/sergei/Desktop/tg_bot` revealed only documentation files (`docs/SRS.md`, `docs/ARCHITECTURE.md`, `docs/DATABASE.md`, `docs/API.md`, `docs/DEPLOYMENT.md`), project metadata (`ORIGINAL_REQUEST.md`, `PROJECT.md`, `TEST_INFRA.md`, `README.md`, `requirements.txt`), and `.agents/`.
   - The entire Python implementation tree (`app/`, `tests/`, `webapp/`) does not yet exist on disk and must be created in accordance with Milestone 1 architectural blueprints.

2. **Authoritative REST API Contracts (`docs/API.md`)**:
   - Lines 4–7 establish:
     ```http
     Базовый URL: https://your-domain.com/api/v1
     Формат данных: application/json
     Авторизация: Заголовок X-Telegram-Init-Data в каждом запросе
     Стандарт ошибок: RFC 7807 (Problem Details for HTTP APIs)
     ```
   - Lines 23–35 specify the RFC 7807 problem details structure:
     ```json
     {
       "type": "https://errors.starosta.app/out-of-bounds",
       "title": "Геолокация вне допустимого радиуса",
       "status": 400,
       "detail": "Вы находитесь на расстоянии 340 м от корпуса Б при лимите 150 м.",
       "instance": "/api/v1/attendance/checkin",
       "data": {
         "distance": 340.5,
         "limit": 150
       }
     }
     ```
   - Lines 41–336 define the 8 key endpoint groups and their precise JSON payload structures:
     - `POST /api/v1/auth/telegram`: `TelegramAuthResponse` with `user`, `permissions`, `current_week`.
     - `GET /api/v1/schedule/today`: `ScheduleTodayResponse` with `pairs` list containing `building_coordinates`, `checkin_status` (`window_start`, `window_end`, `seconds_remaining`, `reason_closed`), and `my_attendance`.
     - `POST /api/v1/attendance/checkin`: `CheckinRequest` (`pair_id`, `client_lat`, `client_lon`, `accuracy`, `timestamp`) $\rightarrow$ `CheckinResponse` (`status="PRESENT"`, `pair_id`, `distance_meters`, `checkin_time`, `message`).
     - `GET /api/v1/attendance/grid/{pair_id}`: `GridResponse` (`pair_id`, `subject`, `is_locked`, `summary`, `students`).
     - `PATCH /api/v1/attendance/override`: `OverrideRequest` (`pair_id`, `student_id`, `new_status`, `excuse_reason`) $\rightarrow$ `OverrideResponse`.
     - `POST /api/v1/attendance/lock/{pair_id}`: `LockPairResponse`.
     - `POST /api/v1/alerts/broadcast`: `BroadcastRequest` $\rightarrow$ `BroadcastResponse` (202 Accepted).
     - `POST /api/v1/reports/export`: `ReportExportRequest` $\rightarrow$ `ReportExportResponse`.

3. **Peer Explorer Interfaces**:
   - `explorer_m1_1` established the 7 SQLAlchemy 2.0 async mapped models (`students`, `subjects`, `schedule_slots`, `pairs_registry`, `attendance`, `broadcast_messages`, `audit_log`), SQLite WAL PRAGMAs, and seed data in `app/database/`.
   - `explorer_m1_2` established cryptographic functions in `app/core/security.py` (`validate_telegram_init_data`), Haversine validation in `app/core/geo.py` (`verify_geocheckin`, `haversine_distance`), and academic timetable utilities in `app/core/time_utils.py` (`get_current_week_info`, `calculate_checkin_window`).

4. **Testing Expectations (`TEST_INFRA.md`)**:
   - Lines 30–36 specify opaque-box testing using `httpx.AsyncClient(app=app, base_url="http://test")` directly against the FastAPI ASGI instance.

---

## 2. Logic Chain

1. **Schema Standardization (Observation 2 $\rightarrow$ Logic Step 1)**:
   Because the TMA SPA and E2E test suite interact with the API via JSON payloads, all incoming requests and outgoing responses must be strictly typed using Pydantic v2. Models representing database entities require `model_config = ConfigDict(from_attributes=True)` to serialize SQLAlchemy models seamlessly. The schemas were modularized into 8 dedicated domain files in `app/schemas/` and indexed in `app/schemas/__init__.py`.

2. **Error Handling Architecture (Observation 2 $\rightarrow$ Logic Step 2)**:
   Because `docs/API.md` mandates RFC 7807 Problem Details for all non-2xx responses, custom exceptions (`ProblemException`), standard `HTTPException`, Pydantic 422 errors (`RequestValidationError`), and unhandled 500 exceptions must all be transformed into uniform `application/problem+json` payloads. This was achieved by creating a `ProblemDetail` schema, defining a catalog of standard error URIs (`ProblemType`), and registering four global exception handlers in `setup_exception_handlers(app)`.

3. **Dependency Injection & Security (Observations 2, 3 $\rightarrow$ Logic Step 3)**:
   Every protected endpoint relies on the `X-Telegram-Init-Data` header. In `app/api/deps.py`:
   - `get_db()` guarantees clean session lifecycle (rollback on error, close on finally).
   - `get_validated_init_data()` cryptographically validates the header using HMAC-SHA256 and rejects data older than 24 hours (RFC 7807 status 401).
   - `get_current_user()` queries the SQLite `students` table by `telegram_id` (RFC 7807 status 403 if unlinked).
   - `get_current_active_student()` rejects `PENDING` and `BLOCKED` accounts (RFC 7807 status 403).
   - `require_roles()` dynamically enforces 3-tier RBAC (`STUDENT`, `ZAM`, `STAROSTA`).

4. **Endpoint Business Logic (Observations 2, 3 $\rightarrow$ Logic Step 4)**:
   - `schedule/today`: Computes ISO weekday, resolves week parity (`ODD`/`EVEN`), filters by student subgroup (0 and student's subgroup), dynamically ensures `pairs_registry` records exist, and computes real-time checkin window availability.
   - `attendance/checkin`: Validates GPS accuracy ($\le 50.0$ m), clock drift ($\le 30$ s), pair lock status, check-in window ($[-5\text{ min} \dots +15\text{ min}]$), and Haversine distance ($\le 150.0$ m) before persisting attendance as `PRESENT`.
   - `attendance/grid/{pair_id}`: Assembles the student attendance matrix with color badges (`green`, `grey`, `yellow`, `blue`, `purple`) and counts summary statistics.
   - `attendance/override`: Allows ZAM and STAROSTA to alter student attendance and records immutable audit trail entries in `audit_log`.
   - `attendance/lock/{pair_id}`: Strictly restricted to STAROSTA, locks the pair journal and records an audit log.
   - `alerts/broadcast`: Queues emergency and info broadcasts; CRITICAL type is strictly restricted to STAROSTA.
   - `reports/export`: Calculates period statistics for Dean's office report generation.

5. **Lifespan, CORS & Static Assets (Observations 1, 4 $\rightarrow$ Logic Step 5)**:
   In `app/main.py`:
   - `@asynccontextmanager async def lifespan(app: FastAPI)` guarantees that `data/` and `data/backups/` directories exist, triggers `Base.metadata.create_all` to instantiate SQLite tables, and invokes idempotent seed data loading before accepting traffic.
   - `CORSMiddleware` permits Telegram webviews (`web.telegram.org`, `settings.FRONTEND_URL`) to communicate with credentials and custom headers.
   - `StaticFiles` mounts `webapp/` at `/webapp` with an automatic root redirect for single-process hosting.

---

## 3. Caveats

1. **Direct Telegram Bot API Integration**: While endpoints (`/alerts/broadcast`, `/reports/export`) record database entities and calculate recipient queues, live outbound Telegram HTTP requests depend on the aiogram bot instance running in Milestone 2.
2. **Dynamic Pairs Initialization**: On days when classes occur, `GET /schedule/today` lazily initializes missing `pairs_registry` rows for that calendar date. This avoids requiring a separate daily pre-generation cron job, though an external cron can also be configured.
3. **Timezone Assumption**: All schedule window calculations assume `Europe/Moscow` (BSPU university timezone) unless overridden via `.env`.

---

## 4. Conclusion

The architectural design for Milestone 1 FastAPI REST API and Lifespan is complete, fully specified, and thoroughly documented in `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_3/m1_api_report.md`.

All 18+ Pydantic v2 schemas, RFC 7807 error handlers, dependency injection chains, endpoint handlers, and application factory with lifespan hooks are ready for immediate implementation in `app/`.

---

## 5. Verification Method

1. **Inspect Report Artifact**:
   - Review `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_3/m1_api_report.md` for complete code listings and architectural specifications.
2. **Schema & Model Consistency**:
   - Verify that model attributes in `app/schemas/attendance.py`, `app/schemas/schedule.py`, etc., correspond 1:1 with fields defined in `docs/API.md` and database models in `docs/DATABASE.md`.
3. **Automated Test Execution (once implemented)**:
   - Run: `pytest -v tests/test_health.py tests/test_auth.py tests/test_attendance.py`
   - Invalidation condition: Any endpoint returning non-RFC 7807 JSON on 4xx/5xx status codes, failure to reject unlinked Telegram IDs with 403, or failure to reject out-of-bounds coordinates ($d > 150$ m) with status 400.
