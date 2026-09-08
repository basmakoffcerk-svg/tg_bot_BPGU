## 2026-09-08T15:09:36Z
You are test_writer_e2e. Your working directory is: /Users/sergei/Desktop/tg_bot/.agents/test_writer_e2e
Authoritative Requirements: /Users/sergei/Desktop/tg_bot/.agents/ORIGINAL_REQUEST.md
Test Infrastructure Specification: /Users/sergei/Desktop/tg_bot/TEST_INFRA.md
Project Blueprint: /Users/sergei/Desktop/tg_bot/PROJECT.md
Documentation: /Users/sergei/Desktop/tg_bot/docs/

Task:
Design and write the comprehensive opaque-box E2E test suite for «АРМ Старосты» strictly based on user requirements and TEST_INFRA.md.
You own the `tests/` directory and `TEST_READY.md`.
1. Update `requirements.txt` if needed to ensure `pytest`, `pytest-asyncio`, `httpx` are listed.
2. Implement `tests/conftest.py`:
   - Pytest async configuration (`asyncio_mode = "auto"`).
   - Mock Telegram initData generator producing authentic HMAC-SHA256 signatures for testing.
   - Temporary SQLite database engine fixtures with WAL mode.
   - HTTPX `AsyncClient` fixture wired to FastAPI application.
3. Implement test modules covering Tiers 1-4:
   - `tests/test_health.py`: Healthcheck status, DB connectivity.
   - `tests/test_auth.py`: HMAC-SHA256 valid signature, invalid signature, missing hash, expired auth_date (>24h), RBAC permissions for STUDENT, ZAM, STAROSTA.
   - `tests/test_geo.py`: Haversine calculation, exact distance boundaries (149m vs 151m), accuracy limits (49m vs 51m), clock drift checks (29s vs 31s).
   - `tests/test_attendance.py`: Schedule today with subgroup filtering, checkin window (-5m to +15m), out of bounds rejection, grid endpoint, manual override with reason, pair lock by starosta and rejection of zam/student.
   - `tests/test_excel.py`: Excel workbook generation with openpyxl, verify sheets, 2-tier header, `=COUNTIF(...) * 2` and `=SUM(...)` formulas, formatting styles.
   - `tests/test_bot.py`: Whitelist registration, inline approve/reject callbacks, broadcast handling.
   - `tests/test_e2e.py`: Tier 4 multi-step scenarios (student full journey, starosta attendance session, weekly cycle, spoofing attempts).
4. Verify total test count meets the thresholds in TEST_INFRA.md (>= 200 tests).
5. When complete, publish `/Users/sergei/Desktop/tg_bot/TEST_READY.md` summarizing test counts per tier.
6. Write your handoff to `/Users/sergei/Desktop/tg_bot/.agents/test_writer_e2e/handoff.md` and send a message.
