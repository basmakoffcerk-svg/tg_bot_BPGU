# Test Suite Verification Report: «АРМ Старосты» (Group 240326 «Матинф» БГПУ)

**Date**: 2026-09-08  
**Author**: `test_writer_e2e`  
**Status**: `READY` (100% Passing)  
**Execution Command**: `.venv/bin/pytest -v`  

---

## 1. Summary of Results
| Metric | Threshold (TEST_INFRA.md) | Actual Count | Result |
|---|:---:|:---:|:---:|
| **Tier 1: Core Feature Happy Paths** | $\ge 90$ | 95 | PASS |
| **Tier 2: Boundary & Error Handling (BVA)** | $\ge 90$ | 92 | PASS |
| **Tier 3: Pairwise Combinatorial Interactions** | $\ge 20$ | 21 | PASS |
| **Tier 4: Real-World E2E Workload Scenarios** | $\ge 5$ | 5 | PASS |
| **Total Test Suite Count** | **$\ge 205$** | **213** | **PASS (100%)** |

---

## 2. Test Breakdown by Module

### 2.1. `tests/test_health.py` (13 tests)
- Healthcheck status HTTP 200 OK and telemetry data.
- Database connectivity check (`SELECT 1`).
- ISO-format UTC timestamp validation.
- SQLite Write-Ahead Logging (`PRAGMA journal_mode = WAL`).
- SQLite foreign key enforcement (`PRAGMA foreign_keys = ON`).
- SQLite concurrency timeouts (`PRAGMA busy_timeout = 5000`).
- SQLite synchronous mode (`PRAGMA synchronous = NORMAL`).
- Concurrency read test without blocking.

### 2.2. `tests/test_auth.py` (29 tests)
- Authentic HMAC-SHA256 validation against `b"WebAppData"` secret key per Telegram WebApp specification.
- Query-string parameter alphabetical sorting verification.
- Tampered payload, modified user ID, corrupted signature rejection (401 Unauthorized).
- Missing `hash` parameter detection (401 Unauthorized).
- Expiration checks: `auth_date` > 24 hours (86,400 s) rejection (401 Unauthorized).
- Future `auth_date` (> 300 s) anti-spoofing rejection (401 Unauthorized).
- Replay attack rejection.
- RBAC permissions matrix for `STUDENT`, `ZAM`, and `STAROSTA`.
- Pending registration account gate (403 Forbidden).

### 2.3. `tests/test_geo.py` (31 tests)
- Spherical Haversine trigonometry verification ($R = 6,371,000$ m).
- Exact boundary distance analysis:
  - Inside building: $d = 25$ m (200 OK).
  - Exact boundary: $d = 149$ m and $d = 150$ m (200 OK).
  - Boundary violation: $d = 151$ m and $d = 350$ m (400 Bad Request, `OUT_OF_BOUNDS`).
- GPS accuracy sensor filter:
  - Exact boundary: $\text{accuracy} = 49$ m and $50$ m (200 OK).
  - Boundary violation: $\text{accuracy} = 51$ m and $150$ m (400 Bad Request, `INACCURATE_GPS`).
- Device clock drift anti-spoofing filter:
  - Permitted drift: $\Delta t = 0$ s and $29$ s (200 OK).
  - Disallowed drift: $\Delta t = 31$ s and $3600$ s (400 Bad Request, `CLOCK_SKEW`).
- Multi-building coordinate checks (Main Building vs Building B).

### 2.4. `tests/test_attendance.py` (31 tests)
- Subgroup schedule filtering (subgroups 0, 1, 2).
- Check-in window calculations ($[-5\text{ min} \dots +15\text{ min}]$ from pair start).
- Window boundaries: $-6$ min (TOO_EARLY) and $+16$ min (TIME_EXPIRED).
- Interactive Chessboard matrix endpoint (`GET /api/v1/attendance/grid/{pair_id}`).
- Badge color mapping: `PRESENT` (green), `MANUAL_CONFIRM` (yellow), `ABSENT_EXCUSED` (purple), `LATE` (blue), `ABSENT_UNEXCUSED` (grey).
- Starosta and Deputy status override (`PATCH /api/v1/attendance/override`) with reason note.
- Immutable audit trail generation (`audit_log` table).
- Pair lock mechanism (`POST /api/v1/attendance/lock/{pair_id}`) restricted strictly to `STAROSTA`.
- Post-lock check-in rejection (`pair-locked`).

### 2.5. `tests/test_excel.py` (31 tests)
- Official BSPU Dean's Office Excel generation with `openpyxl`.
- Sheet naming (`Рапортичка 240326`) and university title headers.
- 2-Tier header layout: Days of Week (merged cols) + Pair numbers 1..6.
- Alphabetical student ordering and 1..N numbering.
- Dynamic formulas:
  - Unexcused hours: `=COUNTIF(C{r}:AL{r}, "Н") * 2`.
  - Excused hours: `=COUNTIF(C{r}:AL{r}, "У") * 2`.
  - Total student hours: `=SUM(AM{r}:AN{r})`.
  - Group total summary row: `=SUM(...)`.
- Cell styling, fonts (Calibri bold), borders, and fills.
- Corner cases: all present, all absent, all excused, all late, single student, empty group.
- Export endpoint (`POST /api/v1/reports/export`).

### 2.6. `tests/test_bot.py` (28 tests)
- `/start` command dispatch for active students (Main Menu).
- `/start` command for unassigned Telegram users showing unclaimed whitelist.
- Student name claim reservation (`PENDING` state).
- 1-Click starosta inline approval (`approve:<student_id>:<tg_id>`) activating user.
- 1-Click starosta inline rejection (`reject:<student_id>:<tg_id>`).
- Non-starosta callback rejection.
- Emergency broadcasting (`POST /api/v1/alerts/broadcast`):
  - `CRITICAL` alerts (@all + personal DM) starosta-only.
  - `INFO` announcements (group chat).
  - Recipient counts matching active student roster.
  - XSS / special characters escaping and length stress.

### 2.7. `tests/test_e2e.py` (50 tests)
- **Scenario 1**: Full Student Onboarding & Geocheckin Journey.
- **Scenario 2**: Starosta Attendance Session with Chessboard & Pair Lock.
- **Scenario 3**: Weekly Dean Report Auto Delivery Cycle with Formula Integrity.
- **Scenario 4**: Adversarial Spoofing & RBAC Attack Suite (coordinates, accuracy, timestamps, role elevation, replay attacks).
- **Scenario 5**: Emergency Alert Broadcast Lifecycle.
- **Pairwise Matrix**:
  - Role $\times$ Protected Endpoint Authorization (18 combinations).
  - GPS Distance $\times$ Accuracy Sensor Matrix (9 combinations).
  - Student Subgroup $\times$ Pair Subgroup Matrix (6 combinations).
  - Academic Bell Schedule Ring Times (6 combinations).
  - Week Parity Matching (3 combinations).
  - 25-Student Simultaneous Check-in Burst (NFR §8.1 Concurrency).

---

## 3. How to Run the Tests
```bash
# Activate virtual environment
source .venv/bin/activate

# Execute full test suite
pytest -v

# Execute specific module
pytest -v tests/test_geo.py
```
