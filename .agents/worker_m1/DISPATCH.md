## 2026-09-08T15:15:13Z
You are worker_m1. Your working directory is: /Users/sergei/Desktop/tg_bot/.agents/worker_m1
Authoritative Requirements: /Users/sergei/Desktop/tg_bot/.agents/ORIGINAL_REQUEST.md
Project Blueprint: /Users/sergei/Desktop/tg_bot/PROJECT.md

Explorer findings to implement:
- Database architecture & models: /Users/sergei/Desktop/tg_bot/.agents/explorer_m1_1/m1_db_report.md
- Security, HMAC-SHA256 & Geo engine: /Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/m1_security_geo_report.md
- FastAPI REST API & Lifespan: /Users/sergei/Desktop/tg_bot/.agents/explorer_m1_3/m1_api_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

File Ownership:
You exclusively own all files inside `/Users/sergei/Desktop/tg_bot/app/`. DO NOT modify files in `tests/` (owned by test writer).

Task:
Implement Milestone 1 (Core Backend & Database) completely and genuinely:
1. Setup Python virtual environment if needed (`uv venv --python 3.11 .venv` and `uv pip install -r requirements.txt` or `source .venv/bin/activate`).
2. Implement `app/config.py` using `pydantic-settings` with defaults matching `.env.example`.
3. Implement `app/database/models.py` (all 7 SQLAlchemy 2.0 async mapped tables: students, subjects, schedule_slots, pairs_registry, attendance, broadcast_messages, audit_log).
4. Implement `app/database/connection.py` with SQLite WAL mode PRAGMAs (`journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`, `foreign_keys=ON`, `cache_size=-64000`) on SQLite connect, async engine, and `get_session`.
5. Implement `app/database/seed.py` with seed data for Group 240326 (29 students with Starosta Ivanov and Zam Kuznetsova, 15 subjects, 21 schedule slots with BSPU coordinates).
6. Implement `app/core/security.py` (HMAC-SHA256 initData validation with `b"WebAppData"`, `auth_date` <= 24h, constant-time compare, RBAC dependencies `get_current_user`, `get_current_active_student`, `require_zam_or_starosta`, `require_starosta`).
7. Implement `app/core/geo.py` (spherical Haversine calculation, R=6,371,000 m, accuracy <= 50m filter, radius <= 150m filter, clock drift <= 30s filter).
8. Implement `app/core/time_utils.py` (academic week calculation, ODD/EVEN parity, study day check, checkin window [-5m ... +15m]).
9. Implement `app/schemas/` with complete Pydantic v2 models for all requests, responses, and RFC 7807 problem details.
10. Implement `app/api/deps.py`, `app/api/router.py`, and endpoints in `app/api/endpoints/` (`health.py`, `auth.py`, `schedule.py`, `attendance.py`, `alerts.py`, `reports.py`).
11. Implement `app/main.py` with FastAPI lifespan initializing tables and seeding on startup, CORS middleware, and static files mount for `webapp/`.
12. Verify your implementation by running a smoke test / Python script that creates the tables, inserts seeds, tests healthcheck and auth endpoints, and confirms zero import or runtime errors.

Document your commands, results, and verification in `/Users/sergei/Desktop/tg_bot/.agents/worker_m1/handoff.md`.
When finished, send a message to orchestrator with your status and summary.
