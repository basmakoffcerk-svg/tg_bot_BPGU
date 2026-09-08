# DISPATCH — explorer_m1_2
Assigned task: Deep dive into Security & Geolocation architecture: HMAC-SHA256 initData validation, 3-tier RBAC dependencies, and Haversine geo verification for Milestone 1.

## 2026-09-08T15:09:36Z
Perform deep architectural exploration for Milestone 1 Security, Geolocation & Utilities:
1. Cryptographic HMAC-SHA256 initData validation in `app/core/security.py`:
   - Parsing query string, extracting hash, validating 24h auth_date freshness.
   - Secret key derivation: `hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()`.
   - Data check string sorting and constant-time comparison `hmac.compare_digest`.
   - FastAPI dependencies: `get_current_user`, `get_current_active_student`, `require_zam_or_starosta`, `require_starosta`.
2. Haversine distance engine in `app/core/geo.py`:
   - Formula with $R = 6,371,000$ m, client accuracy filter ($accuracy \le 50.0$ m), distance filter ($d \le 150.0$ m).
3. Academic time and schedule logic in `app/core/time_utils.py`:
   - Week parity calculation (ODD/EVEN from reference semester start date).
   - Checkin window calculation ($[-5\text{ min} \dots +15\text{ min}]$ from pair start).
4. Document full implementation details in `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/m1_security_geo_report.md`.
5. Write handoff to `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/handoff.md` and notify orchestrator.
