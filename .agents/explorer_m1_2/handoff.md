# Handoff Report — Milestone 1 Security, Geolocation & Utilities

**Agent:** `explorer_m1_2`  
**Working Directory:** `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2`  
**Task:** Deep architectural exploration for Milestone 1 Security, Geolocation & Utilities  
**Target Files:** `app/core/security.py`, `app/core/geo.py`, `app/core/time_utils.py`  
**Primary Deliverable:** `/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/m1_security_geo_report.md`  

---

## 1. Observation

Direct observations and findings from the codebase and documentation:

1. **Security & Cryptography (`docs/ARCHITECTURE.md:157-190`, `docs/API.md:13-20`, `docs/SRS.md:184-186`)**:
   - `docs/ARCHITECTURE.md` line 182 specifies secret key derivation:
     ```python
     secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
     ```
   - Parameter pairs (excluding `hash`) must be sorted lexicographically and formatted as `key=value\n`:
     ```python
     data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
     ```
   - Constant-time comparison is mandatory:
     ```python
     hmac.compare_digest(calculated_hash, received_hash)
     ```
   - `docs/SRS.md` line 185 and `docs/ARCHITECTURE.md` line 70 specify 24-hour expiration (`auth_date` freshness $\le 86,400$ s).
   - FastAPI request authentication relies on the header `X-Telegram-Init-Data: <raw_querystring>`.
   - The RBAC model (`docs/SRS.md:40-53`) identifies three distinct roles: `STUDENT`, `ZAM`, and `STAROSTA`.

2. **Haversine Geolocation Engine (`docs/SRS.md:103-110`, `docs/API.md:151-195`)**:
   - `docs/SRS.md` line 105 specifies the exact formula with mean Earth radius:
     $$d = 2R \cdot \arcsin\left(\sqrt{\sin^2\left(\frac{\Delta \varphi}{2}\right) + \cos(\varphi_1)\cos(\varphi_2)\sin^2\left(\frac{\Delta \lambda}{2}\right)}\right), \quad R = 6,371,000\text{ m}$$
   - `docs/SRS.md` line 102 and `docs/API.md` line 167: Sensor accuracy gate requires $\text{accuracy} \le 50.0$ m (otherwise error `INACCURATE_GPS`).
   - `docs/SRS.md` line 108 and `docs/API.md` line 170: Distance gate requires $d \le 150.0$ m (otherwise error `OUT_OF_BOUNDS`).
   - `docs/SRS.md` line 188: Sensor timestamp anti-spoofing requires $|\Delta t| \le 30.0$ s relative to server time.

3. **Academic Timetable & Schedule Logic (`docs/SRS.md:78-87`, `docs/API.md:63-68, 88-144`)**:
   - Academic semester start date is `2026-09-01`.
   - `docs/API.md` line 91 confirms that on `2026-09-08` (Tuesday), `week_type` is `"EVEN"` (Week 2, Знаменатель).
   - `docs/API.md` line 64 confirms that on Week 3, `week_type` is `"ODD"` (Числитель).
   - Study days are Monday through Saturday (`day_of_week BETWEEN 1 AND 6`). Sunday is day 7 (`is_study_day = False`).
   - `docs/SRS.md` line 100 and `docs/API.md` lines 109-140 define the check-in window as $[-5\text{ min} \dots +15\text{ min}]$ relative to pair start time.
   - Window status requires reporting `is_active`, `window_start`, `window_end`, `seconds_remaining` (or `seconds_until_start`), and `reason_closed` (`NOT_STARTED_YET`, `TIME_EXPIRED`, `PAIR_LOCKED`).
   - Timezone configuration in `.env.example` line 14 is `TIMEZONE=Europe/Moscow`.

4. **Runtime Verification**:
   - Verification scripts executed via Python 3 confirmed:
     - `validate_telegram_init_data` returns `True` for valid HMAC signatures and `False` for tampered parameters or expired `auth_date`.
     - `haversine_distance` between building (`55.753100, 37.621000`) and client (`55.753140, 37.620950`) evaluates to $5.44$ m ($\le 150.0$ m).
     - Week parity calculation evaluates `2026-09-01` to `(1, 'ODD', True)` and `2026-09-08` to `(2, 'EVEN', True)`.
     - Checkin window for `10:15` evaluates window to `10:10` – `10:30`, accurately tracking active time, early arrival, and expiration.

---

## 2. Logic Chain

1. **Telegram InitData Authentication Pipeline**:
   - *Observation*: Telegram sends raw query strings in the `X-Telegram-Init-Data` header.
   - *Inference*: The server must parse query strings using `urllib.parse.parse_qsl` to auto-decode values before constructing the canonical check string, because Telegram's signature was computed over the decoded values.
   - *Inference*: To prevent timing attacks, hash comparison cannot use standard string equality (`==`); it must strictly use `hmac.compare_digest`.
   - *Inference*: The 24-hour expiration check ($now - auth\_date \le 86400$) combined with a forward skew guard ($auth\_date \le now + 60$) prevents token replaying.
   - *Inference*: Because `/api/v1/auth/telegram` needs to know the Telegram user even if the student is not yet confirmed in the whitelist, the dependency chain must provide both `get_current_telegram_user` (returns `TelegramUser` without DB lookup) and `get_current_user` (returns `Student` from DB).

2. **RBAC Guard Architecture**:
   - *Observation*: The role hierarchy is `STUDENT` < `ZAM` < `STAROSTA`, and students have statuses `PENDING`, `ACTIVE`, `BLOCKED`.
   - *Inference*: Endpoints must enforce active status first via `get_current_active_student` before checking role permissions, preventing pending or banned users from accessing protected data.
   - *Inference*: Higher-privilege actions must use reusable role-checker factories (`require_zam_or_starosta`, `require_starosta`).

3. **Haversine Distance & Anti-Spoofing**:
   - *Observation*: Coordinates represent physical university buildings where GPS signals might suffer from indoor drift.
   - *Inference*: Dual-gate verification is necessary: client accuracy must first be $\le 50.0$ m to ensure reliable sensor data, followed by distance calculation $\le 150.0$ m.
   - *Inference*: In floating point math, $a = \sin^2(\Delta\varphi/2) + \cos(\varphi_1)\cos(\varphi_2)\sin^2(\Delta\lambda/2)$ can exceed 1.0 slightly due to rounding. Clamping $a \in [0.0, 1.0]$ prevents domain errors in `math.asin`.
   - *Inference*: Checking $|t_{server} - t_{sensor}| \le 30.0$ s ensures that coordinates were not recorded earlier and replayed.

4. **Academic Timetable & Schedule Mechanics**:
   - *Observation*: Universities switch parity on Mondays, and `2026-09-08` is Tuesday of Week 2 (`EVEN`).
   - *Inference*: Parity calculation must align both the reference start date and the target date to their respective week's Monday (`date - timedelta(days=date.weekday())`), dividing calendar week differences by 7.
   - *Inference*: Check-in window logic must operate in the local academic timezone (`Europe/Moscow` using `zoneinfo.ZoneInfo`) so daylight saving or system server time differences do not corrupt checkin windows.

---

## 3. Caveats

1. **Database Model Integration**:
   - `app/core/security.py` depends on `app.database.models.Student`, `RoleEnum`, and `StatusEnum`. These models are being concurrently designed by `explorer_m1_1`. The security module imports them from `app.database.models`, which adheres directly to `docs/DATABASE.md`.
2. **Settings Configuration**:
   - The security and geo modules reference `app.config.settings` for `BOT_TOKEN`, `TIMEZONE`, and distance thresholds. If settings are not yet loaded, sensible defaults (`Europe/Moscow`, 150.0m, 50.0m, 86400s) are built-in.
3. **No External Network Dependencies**:
   - The offline mock generator `generate_mock_init_data` allows complete test execution without Telegram Bot API or internet connectivity.

---

## 4. Conclusion

The architectural investigation for Milestone 1 Security, Geolocation & Academic Utilities is complete and fully documented in:
`/Users/sergei/Desktop/tg_bot/.agents/explorer_m1_2/m1_security_geo_report.md`

Key deliverables designed:
- **`app/core/security.py`**: Production-ready implementation of HMAC-SHA256 initData validation, mock generator, and 3-tier RBAC dependency chain.
- **`app/core/geo.py`**: Spherical Haversine distance engine ($R = 6,371,000$ m), sensor accuracy gate ($\le 50.0$ m), distance gate ($\le 150.0$ m), and anti-spoofing timestamp validation ($\le 30$ s).
- **`app/core/time_utils.py`**: Academic calendar week numbering, ODD/EVEN parity calculation, study day detection, and dynamic check-in window calculations ($[-5\text{ min} \dots +15\text{ min}]$).

All interfaces are strictly decoupled, typed, and ready for immediate implementation in Milestone 1.

---

## 5. Verification Method

Independent verification can be performed by running the following commands:

1. **Verify HMAC-SHA256 InitData Validation & Mock Generation**:
   ```bash
   python3 -c "
   import hmac, hashlib, json, time
   from urllib.parse import parse_qsl, urlencode

   bot_token = '1234567890:ABCdefGHIjklMNOpqrsTUVwxyz_12345678'
   params = {'auth_date': str(int(time.time())), 'query_id': 'AAHd_test', 'user': json.dumps({'id': 12345, 'first_name': 'Ivan'})}
   check_str = '\n'.join(f'{k}={v}' for k, v in sorted(params.items()))
   sec_key = hmac.new(b'WebAppData', bot_token.encode(), hashlib.sha256).digest()
   params['hash'] = hmac.new(sec_key, check_str.encode(), hashlib.sha256).hexdigest()
   
   parsed = dict(parse_qsl(urlencode(params)))
   h = parsed.pop('hash')
   c_str = '\n'.join(f'{k}={v}' for k, v in sorted(parsed.items()))
   assert hmac.compare_digest(hmac.new(sec_key, c_str.encode(), hashlib.sha256).hexdigest(), h)
   print('HMAC Validation Verified!')
   "
   ```

2. **Verify Haversine Geolocation Distance ($R = 6,371,000$ m)**:
   ```bash
   python3 -c "
   import math
   R = 6371000.0
   def d(lat1, lon1, lat2, lon2):
       p1, p2 = math.radians(lat1), math.radians(lat2)
       dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
       a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
       return 2.0 * R * math.asin(math.sqrt(min(1.0, a)))
   dist = d(55.753140, 37.620950, 55.753100, 37.621000)
   print(f'Distance: {dist:.2f} m')
   assert dist < 150.0
   print('Haversine Verified!')
   "
   ```

3. **Verify Academic Week Parity and Study Day**:
   ```bash
   python3 -c "
   from datetime import date, timedelta
   def week_info(d, start=date(2026, 9, 1)):
       ref_m = start - timedelta(days=start.weekday())
       target_m = d - timedelta(days=d.weekday())
       w_num = max(1, 1 + (target_m - ref_m).days // 7)
       parity = 'ODD' if w_num % 2 == 1 else 'EVEN'
       is_study = 1 <= (d.weekday() + 1) <= 6
       return w_num, parity, is_study

   assert week_info(date(2026, 9, 1)) == (1, 'ODD', True)
   assert week_info(date(2026, 9, 8)) == (2, 'EVEN', True)
   assert week_info(date(2026, 9, 15)) == (3, 'ODD', True)
   assert week_info(date(2026, 9, 13)) == (2, 'EVEN', False)
   print('Academic Week Parity Verified!')
   "
   ```

**Invalidation Conditions:**
- Modification of secret key derivation key from `b"WebAppData"` to any other value.
- Changing Earth radius constant $R$ from $6,371,000$ m.
- Altering checkin window boundaries from $[-5\text{ min} \dots +15\text{ min}]$.
