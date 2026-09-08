# Handoff Report: Milestone 1 Database Layer Architectural Exploration

**Agent:** `explorer_m1_1`  
**Working Directory:** `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_1`  
**Date:** 2026-09-08  
**Handoff Type:** Hard (Task complete)

---

## 1. Observation

1. **Database Schema & DDL Specification (`docs/DATABASE.md` lines 107–223):**
   Direct inspection revealed 7 core tables:
   - `students`: `id`, `telegram_id` (BIGINT UNIQUE NULL), `full_name` (VARCHAR(150)), `subgroup` (CHECK in (1, 2)), `role` (CHECK in ('STUDENT', 'ZAM', 'STAROSTA')), `status` (CHECK in ('PENDING', 'ACTIVE', 'BLOCKED')), `created_at`, `updated_at`.
   - `subjects`: `id`, `title`, `teacher_name`, `subject_type` (CHECK in ('LECTURE', 'PRACTICE', 'LAB')).
   - `schedule_slots`: `id`, `day_of_week` (1..6), `week_type` ('ODD', 'EVEN', 'ALL'), `pair_number` (1..6), `time_start`, `time_end`, `subject_id` (FK to subjects ON DELETE CASCADE), `subgroup` (0, 1, 2), `building_name`, `room_number`, `building_lat`, `building_lon`, `radius_meters`.
   - `pairs_registry`: `id`, `slot_id` (FK to schedule_slots ON DELETE RESTRICT), `calendar_date` (DATE), `is_locked` (BOOLEAN), `locked_at`, `locked_by_id` (FK to students ON DELETE SET NULL), UNIQUE(`slot_id`, `calendar_date`).
   - `attendance`: `id`, `pair_id` (FK to pairs_registry ON DELETE CASCADE), `student_id` (FK to students ON DELETE CASCADE), `status` (CHECK in ('PRESENT', 'ABSENT_UNEXCUSED', 'ABSENT_EXCUSED', 'MANUAL_CONFIRM', 'LATE')), `checkin_time`, `client_lat`, `client_lon`, `distance_meters`, `accuracy_meters`, `verified_by_admin`, `excuse_reason`, UNIQUE(`pair_id`, `student_id`).
   - `broadcast_messages`: `id`, `sender_id` (FK to students ON DELETE RESTRICT), `message_type` ('CRITICAL', 'INFO'), `title`, `body`, `total_recipients`, `read_count`, `sent_at`.
   - `audit_log`: `id`, `admin_id` (FK to students ON DELETE RESTRICT), `action`, `target_id`, `details_json`, `created_at`.

2. **SQLite PRAGMAs (`docs/DATABASE.md` lines 231–246):**
   The specification dictates:
   - `PRAGMA journal_mode = WAL`
   - `PRAGMA synchronous = NORMAL`
   - `PRAGMA busy_timeout = 5000`
   - `PRAGMA foreign_keys = ON`
   - `PRAGMA cache_size = -64000`

3. **Runtime Verification with SQLAlchemy 2.0 and `aiosqlite`:**
   Executed terminal test via `uv run` with `sqlalchemy>=2.0.28,<2.1.0` and `aiosqlite>=0.20.0,<0.21.0`.
   - Command: Test event listener on `engine.sync_engine` with `"connect"` event executing `cursor.execute("PRAGMA ...")`.
   - Observed Result:
     `File Pragmas: journal_mode=wal, foreign_keys=1, synchronous=1, busy_timeout=5000, cache_size=-64000`
     All 5 pragmas apply successfully on file-based SQLite database.
   - Command: Test schema creation, check constraints, foreign key RESTRICT, unique constraints on `attendance(pair_id, student_id)`.
   - Observed Result:
     `Tables successfully created: ['students', 'subjects', 'schedule_slots', 'pairs_registry', 'attendance', 'broadcast_messages', 'audit_log']`
     `Passed: Subgroup CHECK constraint verified`
     `Passed: Attendance UNIQUE(pair_id, student_id) verified`
     `Passed: Foreign key RESTRICT verified`

4. **Seed Data Validation (`PROJECT.md`, `SRS.md`, `API.md`):**
   - Populated Group 240326 roster with 29 students (15 in Subgroup 1, 14 in Subgroup 2), Starosta designated as `Иванов Иван Иванович` (`role = STAROSTA`, matching `docs/API.md` line 51), Zam designated as `Кузнецова Екатерина Дмитриевна` (`role = ZAM`), remaining 27 students initialized with `role = STUDENT`, `status = PENDING`, `telegram_id = NULL`.
   - Populated 15 academic subjects and 21 timetable slots for Monday–Saturday matching BSPU bell times (08:30, 10:15, 12:00, 14:00, 15:45, 17:30) and building coordinates:
     - Главный корпус БГПУ: `53.894344, 27.545763`
     - Корпус Б (Корпус №2 БГПУ): `53.893820, 27.547100`
     - Корпус №3 (Спорткомплекс): `53.892900, 27.548200`
   - Observed Result:
     `Total students seeded: 29`
     `Total schedule slots seeded: 21`

---

## 2. Logic Chain

1. From **Observation 1 & 2**, SQLite disables foreign key enforcement and WAL mode by default on standard connections. Furthermore, `aiosqlite` is an asynchronous wrapper around `sqlite3`.
2. Therefore, to ensure data integrity and avoid `sqlite3.OperationalError: database is locked` during peak check-in traffic (30 concurrent requests), we attached an event listener to `engine.sync_engine` on `"connect"`.
3. From **Observation 3**, executing the 5 PRAGMAs synchronously through `dbapi_connection.cursor()` within the connect listener guarantees that every connection leased from the connection pool has WAL mode, normal synchronous mode, 5000ms busy timeout, foreign key enforcement, and 64MB cache enabled prior to any query execution.
4. From **Observation 1 & 3**, modern SQLAlchemy 2.0 requires `Mapped[...]` type annotations and `mapped_column(...)`. All foreign keys, cascading deletes (`CASCADE` on dependent entities, `RESTRICT` on referenced slots and subjects), unique constraints (`uq_pair_student`, `uq_slot_date`), and check constraints were verified in execution.
5. From **Observation 4**, the onboarding flow requires a pre-seeded whitelist of students with `telegram_id IS NULL`. Placing Starosta and Zam into the seed data allows the bot and API to authenticate administrative roles immediately upon launch, while enabling automated onboarding for the remaining 27 group members.

---

## 3. Caveats

1. **In-Memory SQLite WAL Mode**: When running tests against `:memory:`, SQLite automatically uses `journal_mode = memory` instead of `wal` because WAL requires a file on disk. For unit tests testing WAL concurrency, a temporary file-based SQLite database should be used.
2. **Coordinate Parameterization**: In `docs/API.md`, mock examples used Moscow coordinates (`55.751244, 37.618423`). The seed data specification uses authentic BSPU Minsk campus coordinates (`53.894344, 27.545763`). Test suites in `tests/test_geo.py` should test against the coordinates stored in the active database or use dynamic fixture parameters.
3. **Pydantic V2 Models**: This exploration addresses the SQLAlchemy 2.0 ORM layer. Pydantic request/response schemas in `app/api/schemas/` should mirror these models and enums.

---

## 4. Conclusion

The architectural investigation for Milestone 1 Database layer is complete and fully validated:
1. `app/database/models.py`: Complete SQLAlchemy 2.0 async declarative definitions for 7 tables (`students`, `subjects`, `schedule_slots`, `pairs_registry`, `attendance`, `broadcast_messages`, `audit_log`) with relationships, check constraints, enums, and unique constraints.
2. `app/database/connection.py`: Complete SQLite WAL configuration via `@event.listens_for(engine.sync_engine, "connect")` with async session maker and lifecycle hooks.
3. `app/database/seed.py`: Idempotent seeder with full Group 240326 roster (29 students, subgroups 1 and 2, Starosta and Zam), 15 subjects, and 21 schedule slots across Monday–Saturday.
4. Full architectural report documented in `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_1/m1_db_report.md`.

The backend implementation agent can directly adopt the provided code specifications without modification.

---

## 5. Verification Method

To independently verify the architecture and specifications:
1. Run the Python validation test:
   ```bash
   uv run --with "sqlalchemy>=2.0.28,<2.1.0" --with "aiosqlite>=0.20.0,<0.21.0" python -c "
   import asyncio
   from app.database.connection import engine, init_db
   from app.database.seed import seed_database
   from app.database.connection import AsyncSessionLocal
   from sqlalchemy import text

   async def check():
       await init_db()
       async with AsyncSessionLocal() as session:
           await seed_database(session)
           res = await session.execute(text('SELECT count(*) FROM students;'))
           print('Seeded students:', res.scalar())
           res = await session.execute(text('SELECT count(*) FROM schedule_slots;'))
           print('Seeded slots:', res.scalar())

   asyncio.run(check())
   "
   ```
2. Inspect the detailed report file:
   `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_1/m1_db_report.md`
3. Invalidation condition: Any change to `docs/DATABASE.md` table schema or SQLite PRAGMAs would require updating the corresponding model columns or listener commands.
