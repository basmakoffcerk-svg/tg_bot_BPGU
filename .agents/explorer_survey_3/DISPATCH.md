# DISPATCH — explorer_survey_3
Assigned task: Analyze system workflows, module integration boundaries, and technical risk factors.

## 2026-09-08T15:05:00Z
Task:
Analyze architecture and system workflows:
1. End-to-end user workflows:
   - Student onboarding flow (Telegram /start -> whitelist check -> request notification to starosta -> 1-click inline button approve/reject -> DB user update -> notify student).
   - Geocheckin flow (Student opens TMA -> gets GPS coordinates -> POST /api/attendance/checkin -> haversine distance & accuracy verification -> status marked as 'present' -> starosta sees real-time status).
   - Starosta chessboard flow (GET /api/attendance/live -> matrix of students x pairs -> click cell to open modal -> change status: уважительная / неуважительная / болеет / опоздал -> lock pair).
   - Automated Excel report generation (weekly/daily schedule via APScheduler -> generate openpyxl report according to dean's office template -> send to starosta/dean via bot).
2. Interface contracts between modules (Bot <-> FastAPI <-> DB <-> WebApp <-> Excel Generator).
3. Concurrency, state management, SQLite WAL configuration, async session lifecycle, potential race conditions or edge cases.
4. Testing strategy recommendations (E2E testing harness, mock Telegram initData generator, test fixtures).

Output:
Write your architecture analysis to:
/Users/sergei/Desktop/tg_bot/.agents/explorer_survey_3/architecture_survey_report.md
Also write a summary handoff in:
/Users/sergei/Desktop/tg_bot/.agents/explorer_survey_3/handoff.md
When finished, send a message to orchestrator with your status and summary.
