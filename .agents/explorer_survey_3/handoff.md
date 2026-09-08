# Handoff Report — explorer_survey_3

## 1. Observation
1. **Repository Specifications**:
   - `ORIGINAL_REQUEST.md`: Lines 20–42 define core requirements R1 (FastAPI + Async SQLAlchemy 2.0 + SQLite WAL), R2 (aiogram 3.x Bot), R3 (TMA SPA frontend), R4 (openpyxl Excel generator + APScheduler).
   - `docs/SRS.md`: Lines 40–53 define strict RBAC (Student, Zam, Starosta); Lines 62–72 specify student onboarding flow via whitelist and starosta 1-click approval; Lines 99–127 specify geocheckin ($R_{valid} \le 150$ m, $accuracy \le 50$ m, window $[-5\text{ min} \dots +15\text{ min}]$) and chessboard overrides; Lines 133–157 specify official BGPU dean report template and Saturday 16:00 cron trigger.
   - `docs/ARCHITECTURE.md`: Lines 13–48 provide C4 container diagram depicting a unified asynchronous modular monolith running under Uvicorn; Lines 158–190 specify the exact Python HMAC-SHA256 cryptographic verification for Telegram `initData`.
   - `docs/DATABASE.md`: Lines 107–224 describe complete DDL schemas (`students`, `subjects`, `schedule_slots`, `pairs_registry`, `attendance`, `broadcast_messages`, `audit_log`); Lines 229–246 specify required SQLite PRAGMAs (`journal_mode=WAL`, `synchronous=NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`, `cache_size=-64000`).
   - `docs/API.md`: Lines 15–336 define 9 REST endpoints adhering to RFC 7807 problem details and `X-Telegram-Init-Data` header authorization.
   - `requirements.txt`: Lines 2–27 list key dependencies: `fastapi`, `uvicorn`, `pydantic`, `aiogram`, `sqlalchemy`, `aiosqlite`, `alembic`, `openpyxl`, `reportlab`, `apscheduler`, `httpx`.
2. **Current Codebase State**:
   - `find_by_name` across `/Users/sergei/Desktop/tg_bot` revealed that only specification docs, `.env.example`, `requirements.txt`, and `.agents/` metadata currently exist. No implementation source files exist yet in `bot/`, `api/`, `models/`, `services/`, `webapp/`, or `tests/`.

## 2. Logic Chain
1. From the requirement for 30 students to check in simultaneously during a 5-second burst (Observation 1, `docs/SRS.md:182`) and SQLite being a single-writer DBMS (Observation 1, `docs/DATABASE.md:231`), standard rollback journal mode would cause transaction lock contention (`sqlite3.OperationalError: database is locked`).
2. Therefore, configuring `PRAGMA journal_mode = WAL` combined with `PRAGMA busy_timeout = 5000` on every aiosqlite connection hook (`connect` event) is mandatory to serialize write transactions without locking out concurrent readers (Analysis report Section 3.1).
3. From the RBAC matrix (`docs/SRS.md:40-53`), only `STAROSTA` is permitted to lock pairs (`/attendance/lock/{pair_id}`) or broadcast critical alerts (`@all` + DM), whereas `ZAM` can view the grid, override statuses with audit logging, and export reports.
4. From the onboarding flow (`docs/SRS.md:62-72`), multiple users could attempt to claim the same student name concurrently. Therefore, an atomic SQL update (`UPDATE students SET telegram_id = :id WHERE id = :target AND telegram_id IS NULL`) with rowcount inspection is required to prevent double-claiming.
5. From the geocheckin requirement (`docs/SRS.md:99-110`), client-side distance calculations cannot be trusted; the server must independently compute the Haversine distance using server-stored building coordinates and enforce the 50 m accuracy threshold.
6. From openpyxl being CPU-bound and synchronous, executing weekly and on-demand report generation directly on the asyncio event loop would freeze FastAPI request handling. Therefore, report generation must run inside `asyncio.to_thread`.
7. Because automated testing cannot rely on a live Telegram client, a deterministic mock `initData` generator with authentic HMAC-SHA256 signing is required to test auth and RBAC in CI/pytest suites (Analysis report Section 4.1).

## 3. Caveats
1. **Network deployment mode**: Polling vs Webhook. In local development or containerized environments without public HTTPS, aiogram Long Polling is simpler; for production behind a reverse proxy (Amvera/VPS), FastAPI webhook handler `/webhook` is recommended.
2. **Offline check-in**: The system requires active mobile internet/GPS during the 20-minute pair window; if a student has no cellular connectivity, the starosta must use the manual override feature (`MANUAL_CONFIRM`).
3. **Report template font compatibility**: Standard Windows/Excel fonts (Calibri/Arial) in openpyxl do not require OS-level font files, but if PDF export via ReportLab is activated later, TrueType Cyrillic fonts must be bundled.

## 4. Conclusion
The architectural design of «АРМ Старосты» is coherent, complete, and robust. All workflows, database schemas, API contracts, concurrency controls, and security models are thoroughly specified.
The detailed survey report has been generated at:
`/Users/sergei/Desktop/tg_bot/.agents/explorer_survey_3/architecture_survey_report.md`
The system is ready for decomposition into implementation milestones (Backend & DB, Telegram Bot, TMA Frontend, Reporting & Scheduler, E2E Testing Harness).

## 5. Verification Method
1. **Report Verification**: Inspect `/Users/sergei/Desktop/tg_bot/.agents/explorer_survey_3/architecture_survey_report.md` for completeness across all 4 requested dimensions.
2. **Schema & Contract Alignment**: Verify that endpoint paths and payload models in the report match `docs/API.md` exactly.
3. **Mock Generator Verification**: Execute the standalone Python mock generator snippet against `validate_telegram_init_data` from `docs/ARCHITECTURE.md:158` to confirm signature validity.
4. **PRAGMA Verification**: Verify that the proposed SQLAlchemy event listener applies the 5 required SQLite PRAGMAs (`WAL`, `NORMAL`, `foreign_keys=ON`, `busy_timeout=5000`, `cache_size=-64000`).
