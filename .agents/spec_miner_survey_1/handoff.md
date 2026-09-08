# HANDOFF REPORT — spec_miner_survey_1

## 1. Observation
1. **Authoritative Requirements (`ORIGINAL_REQUEST.md`, lines 5–52)**:
   - Specifies development of «АРМ Старосты» for academic group 240326 «Матинф» БГПУ with aiogram 3.x, FastAPI, Telegram Mini App (HTML5/JS), and SQLite WAL.
   - Core functional requirements: R1 (Server backend & SQLite DB), R2 (Telegram Bot aiogram 3.x), R3 (TMA SPA frontend), R4 (Official Dean's Office Excel report via openpyxl).
2. **System Requirements & RBAC (`docs/SRS.md`, lines 40–53, 78–127, 133–156)**:
   - Strict RBAC matrix: `STUDENT` (schedule, checkin, stats), `ZAM` (grid view, manual status override with audit log, report export, INFO alerts), `STAROSTA` (pair lock, CRITICAL alerts with @all and DM spam, group whitelist management, appointing deputy).
   - Bell schedule (lines 80–87): 6 pair slots from 08:30 to 19:00. Checkin window (line 100): $[time\_start - 5\text{ мин} \dots time\_start + 15\text{ мин}]$.
   - GPS parameters (lines 102–109): accuracy $\le 50$ m, Haversine formula with $R = 6\,371\,000$ m, allowed radius $d \le 150$ m.
   - Attendance statuses (lines 113–117): `PRESENT` (green), `ABSENT_UNEXCUSED` (gray/red, «Н»), `MANUAL_CONFIRM` (yellow), `LATE` (blue, «О»), `ABSENT_EXCUSED` (purple, «У»).
   - Excel report standards (lines 133–152): openpyxl, dean's header, alphabetical students list, 6 pairs per day (Mon-Sat), formulas: unexcused hours ($COUNTIF \times 2$), excused hours ($COUNTIF \times 2$), total hours, and group totals sum.
3. **Architecture & Security (`docs/ARCHITECTURE.md`, lines 67–80, 158–190)**:
   - Telegram WebApp `initData` validation via HMAC-SHA256: `secret_key = HMAC(b"WebAppData", bot_token)`. Alphabetical sorting of query keys, check `auth_date` freshness $\le 86400$ s (24 hours).
   - Modular monolith directory structure (lines 215–253): `bot/`, `api/`, `core/`, `models/`, `services/`, `webapp/`, `tests/`.
4. **Database Models & Concurrency (`docs/DATABASE.md`, lines 108–223, 231–246)**:
   - 7 relational tables: `students`, `subjects`, `schedule_slots`, `pairs_registry`, `attendance`, `broadcast_messages`, `audit_log`.
   - SQLite WAL configuration: `PRAGMA journal_mode = WAL;`, `PRAGMA synchronous = NORMAL;`, `PRAGMA busy_timeout = 5000;`, `PRAGMA cache_size = -64000;`.
5. **REST API Contracts (`docs/API.md`, lines 41–336)**:
   - 8 API routes: `GET /health`, `POST /auth/telegram`, `GET /schedule/today`, `POST /attendance/checkin`, `GET /attendance/grid/{pair_id}`, `PATCH /attendance/override`, `POST /attendance/lock/{pair_id}`, `POST /alerts/broadcast`, `POST /reports/export`.
   - RFC 7807 error format with specific error codes (`OUT_OF_BOUNDS`, `INACCURATE_GPS`, `CHECKIN_WINDOW_CLOSED`, `PAIR_LOCKED`).
6. **Deployment & Environment (`docs/DEPLOYMENT.md`, lines 66–103)**:
   - Specific environment variables: `BOT_TOKEN`, `STAROSTA_TELEGRAM_ID`, `GROUP_CHAT_ID`, `MAX_ALLOWED_DISTANCE_METERS=150`, `MAX_GPS_ACCURACY_METERS=50`, `CHECKIN_WINDOW_BEFORE_MINUTES=5`, `CHECKIN_WINDOW_AFTER_MINUTES=15`.
   - APScheduler weekly cron: Saturday at 16:00.

## 2. Logic Chain
1. *From Observation 1 & 4*: The requirement for concurrent student checkins without locking conflicts is solved by configuring SQLite in WAL mode with a 5000ms busy timeout and SQLAlchemy 2.0 AsyncEngine.
2. *From Observation 2 & 3*: The requirement for tamper-proof geocheckin is addressed through a three-layer verification chain: (a) Telegram HMAC-SHA256 initData cryptographic validation, (b) GPS sensor accuracy check ($\le 50$ m) and client timestamp delta check ($\le 30$ s), and (c) mathematical spherical distance calculation via Haversine against stored building coordinates ($\le 150$ m).
3. *From Observation 2 & 5*: The administrative requirement for non-repudiation in attendance modifications is satisfied by the `attendance.verified_by_admin` flag, the `audit_log` table storing before/after JSON states, and the strict pair lock endpoint (`POST /attendance/lock/{pair_id}`) restricted exclusively to the `STAROSTA` role.
4. *From Observation 2 & 6*: The administrative burden of manual weekly reporting is eliminated via the dual-mode Excel export service: on-demand generation (`/report` bot command and TMA button) and automated APScheduler cron delivery every Saturday at 16:00.

## 3. Caveats
1. **Implementation Status**: This survey represents a static analysis of requirements and design specifications. Source code in `bot/`, `api/`, `webapp/`, `models/`, and `services/` has not yet been implemented in the repository (only root documentation, `.env.example`, and `requirements.txt` exist).
2. **Initial Group Seed Data**: The exact roster of student names for group 240326 «Матинф» and the specific classroom timetable for the current semester need to be provided or pre-seeded in the database initialization migrations.
3. **External Dependencies**: The deployment architecture assumes external HTTPS termination (Vercel/Cloudflare/ngrok) because the HTML5 Geolocation API and Telegram WebApp SDK strictly require HTTPS.

## 4. Conclusion
All functional requirements, security protocols, mathematical algorithms, data schemas, API contracts, Excel report templates, and Telegram bot interaction flows have been exhaustively documented and synthesized into `/Users/sergei/Desktop/tg_bot/.agents/spec_miner_survey_1/survey_report.md`. The specifications are complete, logically consistent across all 5 architectural documents, and ready for implementation.

## 5. Verification Method
1. **Document Inspection**:
   - Inspect `/Users/sergei/Desktop/tg_bot/.agents/spec_miner_survey_1/survey_report.md` to verify all 7 requested sections and both structured tables (`Features Discovered` and `Edge Cases`).
2. **Schema & Contract Alignment**:
   - Cross-verify section 2 of the report against `docs/DATABASE.md` (7 tables, DDL constraints, WAL pragmas).
   - Cross-verify section 5 of the report against `docs/API.md` (HTTP methods, path parameters, RFC 7807 error structures).
   - Cross-verify section 3 of the report against `docs/ARCHITECTURE.md` (HMAC-SHA256 signature algorithm).
3. **Invalidation Conditions**:
   - The findings would be invalidated if changes are made to the database schema in `docs/DATABASE.md` or the API contracts in `docs/API.md` without corresponding updates to the survey report.
