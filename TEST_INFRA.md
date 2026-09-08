# E2E Test Infra: «АРМ Старосты»

## Test Philosophy
- Opaque-box, requirement-driven, derived strictly from `ORIGINAL_REQUEST.md` and user specifications.
- Methodology: Category-Partition, Boundary Value Analysis (BVA), Pairwise Combinatorial Testing, Real-World Workload Testing.
- Progressive testability: Tests use offline cryptographic mock `initData` generators and `httpx.AsyncClient` against the ASGI application, ensuring zero external network dependency.

## Feature Inventory & Test Mapping
| # | Feature | Requirement Source | Tier 1 (Feature) | Tier 2 (Boundary) | Tier 3 (Pairwise) | Tier 4 (Workload) |
|---|---------|-------------------|:----------------:|:-----------------:|:-----------------:|:-----------------:|
| 1 | Onboarding & Whitelist | ORIGINAL_REQUEST §1, SRS §3.1 | 5 | 5 | ✓ | ✓ |
| 2 | 1-Click Inline Confirmation | ORIGINAL_REQUEST §1, SRS §3.1 | 5 | 5 | ✓ | ✓ |
| 3 | Telegram Menu Button & Launch | ORIGINAL_REQUEST §2, SRS §3.2 | 5 | 5 | ✓ | ✓ |
| 4 | HMAC-SHA256 InitData Auth | ORIGINAL_REQUEST §2, API §2 | 5 | 5 | ✓ | ✓ |
| 5 | 3-Tier RBAC Engine | ORIGINAL_REQUEST §2, SRS §2 | 5 | 5 | ✓ | ✓ |
| 6 | Schedule Grid & Subgroups | ORIGINAL_REQUEST §3, API §3 | 5 | 5 | ✓ | ✓ |
| 7 | Checkin Window Engine | ORIGINAL_REQUEST §3, SRS §3.3 | 5 | 5 | ✓ | ✓ |
| 8 | Haversine Distance Engine | ORIGINAL_REQUEST §3, SRS §3.3 | 5 | 5 | ✓ | ✓ |
| 9 | Dual GPS Accuracy Gate | ORIGINAL_REQUEST §3, SRS §3.3 | 5 | 5 | ✓ | ✓ |
| 10 | Anti-Spoofing & Lock Guards | ORIGINAL_REQUEST §3, API §4 | 5 | 5 | ✓ | ✓ |
| 11 | Interactive Chessboard Grid | ORIGINAL_REQUEST §4, SRS §3.4 | 5 | 5 | ✓ | ✓ |
| 12 | Status Cycle & Excuse Modal | ORIGINAL_REQUEST §4, SRS §3.4 | 5 | 5 | ✓ | ✓ |
| 13 | Pair Lock Mechanism | ORIGINAL_REQUEST §4, API §7 | 5 | 5 | ✓ | ✓ |
| 14 | Dean's Office Excel Generator | ORIGINAL_REQUEST §5, SRS §3.5 | 5 | 5 | ✓ | ✓ |
| 15 | Weekly APScheduler Auto Delivery | ORIGINAL_REQUEST §5, Arch | 5 | 5 | ✓ | ✓ |
| 16 | On-Demand Report Export | ORIGINAL_REQUEST §5, API §9 | 5 | 5 | ✓ | ✓ |
| 17 | Emergency & Info Broadcast | ORIGINAL_REQUEST §6, SRS §3.6 | 5 | 5 | ✓ | ✓ |
| 18 | Healthcheck & Telemetry | API §1 | 5 | 5 | ✓ | ✓ |

## Test Architecture
- **Test Runner**: `pytest -v tests/` using `pytest-asyncio`.
- **Test Clients**: `httpx.AsyncClient(app=app, base_url="http://test")` for API, aiogram `MockedBot` / event dispatcher testing for Telegram Bot.
- **Mock Generators**: Authentic `mock_init_data(user_dict, bot_token, auth_date)` helper generating valid HMAC-SHA256 headers.
- **Database**: SQLite in-memory or temporary file with WAL mode and tables initialized via `Base.metadata.create_all`.
- **Excel Inspection**: `openpyxl.load_workbook(..., data_only=False)` inspecting formulas (`COUNTIF`, `SUM`) and cell styles.

## Real-World Application Scenarios (Tier 4)
1. **Full Student Journey**: Unregistered student `/start` $\rightarrow$ selects name $\rightarrow$ starosta approves $\rightarrow$ student opens TMA $\rightarrow$ checks schedule $\rightarrow$ performs geocheckin ($d=45$ m, $accuracy=15$ m) $\rightarrow$ status becomes `PRESENT`.
2. **Class Attendance Management (Starosta)**: Pair starts $\rightarrow$ 25 students check in via GPS $\rightarrow$ Starosta opens Chessboard $\rightarrow$ sees 25 present, 3 absent $\rightarrow$ sets 1 student to `ABSENT_EXCUSED` with reason $\rightarrow$ sets 1 student to `LATE` $\rightarrow$ locks pair $\rightarrow$ attempts by latecomers rejected.
3. **Weekly Dean Report Cycle**: Group conducts classes throughout the week (Mon–Sat) $\rightarrow$ Saturday 16:00 APScheduler triggers report $\rightarrow$ Excel generated with exact BSPU styling and `=COUNTIF(...) * 2` formulas $\rightarrow$ verified formulas calculate correct total absent hours.
4. **Adversarial Spoofing & RBAC Attacks**: Student tries to check in with forged coordinates ($d=250$ m) $\rightarrow$ rejected; student attempts GPS accuracy spoofing ($accuracy=80$ m) $\rightarrow$ rejected; student attempts unauthorized pair lock $\rightarrow$ 403 Forbidden; replay attack with expired `auth_date` (>24h) $\rightarrow$ 401 Unauthorized.
5. **Emergency Alert Broadcast**: Starosta sends `CRITICAL` alert $\rightarrow$ verified broadcast queued $\rightarrow$ simulated bot delivers personal DMs to all active group members.

## Coverage Thresholds
- Tier 1: $\ge 5$ test cases per feature ($\ge 90$ test cases).
- Tier 2: $\ge 5$ boundary/corner cases per feature ($\ge 90$ test cases).
- Tier 3: Major pairwise interactions ($\ge 20$ test cases).
- Tier 4: $\ge 5$ real-world end-to-end workload scenarios.
- **Total Suite Minimum: $\ge 205$ test cases.**
