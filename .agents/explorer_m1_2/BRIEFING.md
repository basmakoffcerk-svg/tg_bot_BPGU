# BRIEFING — 2026-09-08T15:13:30Z

## Mission
Deep architectural exploration for Milestone 1 Security, Geolocation & Utilities: HMAC-SHA256 initData validation, RBAC dependencies, Haversine geo verification, and Academic time/schedule logic.

## 🔒 My Identity
- Archetype: explorer
- Roles: Security, Geolocation & Utilities Specialist
- Working directory: /Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2
- Original parent: c535a0f4-5f91-43ad-995a-f09dadc735e1
- Milestone: Milestone 1

## 🔒 Key Constraints
- Read-only investigation — do NOT implement directly in app/
- Strictly follow authoritative requirements and existing architecture blueprints
- Maintain clean separation of concerns and exact mathematical/cryptographic correctness

## Current Parent
- Conversation ID: c535a0f4-5f91-43ad-995a-f09dadc735e1
- Updated: 2026-09-08T15:13:30Z

## Investigation State
- **Explored paths**:
  - `/Users/sergei/Desktop/tg_bot/ORIGINAL_REQUEST.md` (R1-R4, Acceptance Criteria)
  - `/Users/sergei/Desktop/tg_bot/PROJECT.md` (Architecture, Milestone 1, Features 4, 5, 7, 8, 9, 10, Layout)
  - `/Users/sergei/Desktop/tg_bot/docs/ARCHITECTURE.md` (C4 containers, Sequence diagrams, HMAC algorithm §3.1, RBAC §3.2)
  - `/Users/sergei/Desktop/tg_bot/docs/API.md` (Headers, RFC 7807 problem details, auth, schedule, checkin)
  - `/Users/sergei/Desktop/tg_bot/docs/SRS.md` (Role matrix §2, Bell schedule §4.1, Haversine equation §5.1, NFR §8.2)
  - `/Users/sergei/Desktop/tg_bot/docs/DATABASE.md` (DDL for students, schedule_slots, pairs_registry, attendance)
  - `/Users/sergei/Desktop/tg_bot/.env.example` & `requirements.txt`
- **Key findings**:
  - HMAC secret key derivation uses `b"WebAppData"` and `bot_token.encode("utf-8")` raw 32-byte digest.
  - Data check string requires alphabetical sorting by key and `\n` join over URL-decoded key-value pairs.
  - Constant-time comparison `hmac.compare_digest` protects against timing attacks.
  - 24h expiration limit (`auth_date`) and 60s future drift guard prevent replay attacks.
  - Haversine formula with $R = 6,371,000$ m and clamp on $a \in [0.0, 1.0]$ prevents domain errors and matches SRS §5.1 exactly.
  - GPS verification has dual gate: sensor accuracy $\le 50.0$ m and distance $\le 150.0$ m, plus $\le 30$ s timestamp drift.
  - Academic timetable: Semester reference date `2026-09-01` produces Week 1 ODD (Sept 1), Week 2 EVEN (Sept 8), Week 3 ODD (Sept 15), matching `docs/API.md`.
  - Checkin window: $[-5\text{ min} \dots +15\text{ min}]$ relative to pair start time in `Europe/Moscow`.
- **Unexplored areas**: None within the assigned Milestone 1 scope.

## Key Decisions Made
- Designed complete production blueprints for `app/core/security.py`, `app/core/geo.py`, and `app/core/time_utils.py`.
- Formulated an offline mock initData generator (`generate_mock_init_data`) for hermetic testing.
- Used Python standard library `zoneinfo` (`ZoneInfo("Europe/Moscow")`) for timezone safety.
- Created `m1_security_geo_report.md` with complete code, mathematical proofs, and test vectors.

## Artifact Index
- `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/DISPATCH.md` — Task history
- `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/BRIEFING.md` — Working memory
- `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/progress.md` — Progress and liveness heartbeat
- `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/m1_security_geo_report.md` — Architectural exploration report
- `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/handoff.md` — 5-component handoff report
