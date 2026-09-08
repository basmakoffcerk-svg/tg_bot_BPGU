# DISPATCH — spec_miner_survey_1
Assigned task: Mine authoritative specifications from docs/ and ORIGINAL_REQUEST.md.

## 2026-09-08T15:05:00Z
You are spec_miner_survey_1. Your working directory is: /Users/sergei/Desktop/tg_bot/.agents/spec_miner_survey_1
Authoritative Requirements: /Users/sergei/Desktop/tg_bot/.agents/ORIGINAL_REQUEST.md
Documentation specifications in the project:
- /Users/sergei/Desktop/tg_bot/docs/SRS.md
- /Users/sergei/Desktop/tg_bot/docs/ARCHITECTURE.md
- /Users/sergei/Desktop/tg_bot/docs/DATABASE.md
- /Users/sergei/Desktop/tg_bot/docs/API.md
- /Users/sergei/Desktop/tg_bot/docs/DEPLOYMENT.md

Task:
Perform exhaustive specification mining across ORIGINAL_REQUEST.md and all docs/*.
Extract and document:
1. Complete Feature Inventory (every functional requirement, user journey, and edge case).
2. Data models, tables, columns, relations, constraints (Users, Whitelist, Groups, Pairs/Schedule, Attendance Records, etc.).
3. Telegram initData HMAC-SHA256 crypto validation spec and RBAC rules (Starosta vs Student vs Deputy).
4. Haversine Geocheckin algorithm, university building coordinates, accuracy (<=50m) and radius (<=150m) criteria, pairs timing and check-in window.
5. REST API endpoints, methods, request bodies, response schemas, error responses from docs/API.md.
6. Dean's office Excel report formatting, sheet structures, openpyxl styles, formulas, and delivery schedule.
7. Telegram Bot interaction specs: onboarding flow, whitelist checking, 1-click inline approval, Mini App launch, alerts broadcast, excel report command.

Output:
Write your comprehensive specification report to:
/Users/sergei/Desktop/tg_bot/.agents/spec_miner_survey_1/survey_report.md
Also write a summary handoff in:
/Users/sergei/Desktop/tg_bot/.agents/spec_miner_survey_1/handoff.md
When finished, send a message to orchestrator with your status and summary.
