# СПЕЦИФИКАЦИЯ REST API ДЛЯ TELEGRAM MINI APP (API)

## Проект: АРМ Старосты («Пульт управления группой 240326»)
**Базовый URL:** `https://your-domain.com/api/v1`  
**Формат данных:** `application/json`  
**Авторизация:** Заголовок `X-Telegram-Init-Data` в каждом запросе  
**Стандарт ошибок:** RFC 7807 (Problem Details for HTTP APIs)

---

## 1. Авторизация и заголовки

Все запросы из Telegram Mini App обязаны содержать заголовок `X-Telegram-Init-Data`, полученный из `window.Telegram.WebApp.initData`.

```http
GET /api/v1/schedule/today HTTP/1.1
Host: your-domain.com
Accept: application/json
X-Telegram-Init-Data: query_id=AAHd...&user=%7B%22id%22%3A123456789...%7D&auth_date=1694178000&hash=5a9b...
```

### Стандартный формат ошибки (RFC 7807):
```json
{
  "type": "https://errors.starosta.app/out-of-bounds",
  "title": "Геолокация вне допустимого радиуса",
  "status": 400,
  "detail": "Вы находитесь на расстоянии 340 м от корпуса Б при лимите 150 м.",
  "instance": "/api/v1/attendance/checkin",
  "data": {
    "distance": 340.5,
    "limit": 150
  }
}
```

---

## 2. Группа эндпоинтов: Аутентификация и профиль

### 2.1. `POST /auth/telegram`
Первичная валидация `initData` при запуске веб-приложения и получение профиля текущего пользователя.

- **Роли:** Любая (включая неавторизованных)
- **Response 200 OK:**
```json
{
  "user": {
    "id": 14,
    "telegram_id": 987654321,
    "full_name": "Иванов Иван Иванович",
    "subgroup": 1,
    "role": "STAROSTA",
    "status": "ACTIVE"
  },
  "permissions": {
    "can_view_grid": true,
    "can_override_status": true,
    "can_lock_pairs": true,
    "can_broadcast_critical": true,
    "can_export_reports": true
  },
  "current_week": {
    "week_number": 3,
    "week_type": "ODD",
    "is_study_day": true
  }
}
```

- **Response 401 Unauthorized:**
```json
{
  "title": "Недействительная подпись initData",
  "status": 401,
  "detail": "Подпись данных Telegram не прошла криптографическую проверку HMAC-SHA256."
}
```

---

## 3. Группа эндпоинтов: Расписание

### 3.1. `GET /schedule/today`
Возвращает список пар на текущий день для подгруппы текущего студента.

- **Роли:** `STUDENT`, `ZAM`, `STAROSTA`
- **Response 200 OK:**
```json
{
  "date": "2026-09-08",
  "day_of_week": 2,
  "week_type": "EVEN",
  "pairs": [
    {
      "pair_id": 102,
      "pair_number": 1,
      "time_start": "08:30",
      "time_end": "10:00",
      "subject": "Высшая математика",
      "teacher": "Смирнов А. В.",
      "type": "LECTURE",
      "room": "304",
      "building": "Главный корпус",
      "building_coordinates": {
        "lat": 55.751244,
        "lon": 37.618423
      },
      "checkin_status": {
        "is_active": false,
        "window_start": "08:25",
        "window_end": "08:45",
        "reason_closed": "TIME_EXPIRED"
      },
      "my_attendance": {
        "status": "PRESENT",
        "distance": 42.1,
        "checkin_time": "2026-09-08T08:34:12"
      }
    },
    {
      "pair_id": 103,
      "pair_number": 2,
      "time_start": "10:15",
      "time_end": "11:45",
      "subject": "Операционные системы (Лаб)",
      "teacher": "Козлов Д. С.",
      "type": "LAB",
      "room": "212-Б",
      "building": "Корпус Б",
      "building_coordinates": {
        "lat": 55.753100,
        "lon": 37.621000
      },
      "checkin_status": {
        "is_active": true,
        "window_start": "10:10",
        "window_end": "10:30",
        "seconds_remaining": 540
      },
      "my_attendance": null
    }
  ]
}
```

---

## 4. Группа эндпоинтов: Посещаемость и Геочекин

### 4.1. `POST /attendance/checkin`
Отправка координат студента для фиксации присутствия.

- **Роли:** `STUDENT`, `ZAM`, `STAROSTA`
- **Request Body:**
```json
{
  "pair_id": 103,
  "client_lat": 55.753140,
  "client_lon": 37.620950,
  "accuracy": 18.5,
  "timestamp": 1725801900
}
```

- **Валидация бэкенда:**
  - `accuracy <= 50.0` (иначе `400 INACCURATE_GPS`).
  - Текущее время попадает в интервал `[time_start - 5 мин ... time_start + 15 мин]` (иначе `400 CHECKIN_WINDOW_CLOSED`).
  - Пара не заблокирована (`is_locked == false`).
  - Расстояние по формуле гаверсинусов $d \le 150.0$ м.

- **Response 200 OK:**
```json
{
  "status": "PRESENT",
  "pair_id": 103,
  "distance_meters": 32.4,
  "checkin_time": "2026-09-08T10:17:34",
  "message": "Присутствие успешно подтверждено!"
}
```

- **Response 400 Bad Request (Вне аудитории):**
```json
{
  "type": "https://errors.starosta.app/out-of-bounds",
  "title": "Геолокация вне аудитории",
  "status": 400,
  "detail": "Вы находитесь вне аудиторного фонда.",
  "data": {
    "distance": 312.8,
    "max_allowed": 150.0
  }
}
```

---

## 5. Группа эндпоинтов: Шахматка старосты (Административные)

### 5.1. `GET /attendance/grid/{pair_id}`
Получение сетки посещаемости группы на выбранную пару.

- **Роли:** `STAROSTA`, `ZAM`
- **Response 200 OK:**
```json
{
  "pair_id": 103,
  "subject": "Операционные системы (Лаб)",
  "is_locked": false,
  "summary": {
    "total_students": 28,
    "present_count": 24,
    "absent_unexcused_count": 3,
    "absent_excused_count": 1,
    "manual_confirmed_count": 1
  },
  "students": [
    {
      "student_id": 1,
      "full_name": "Александров Александр",
      "subgroup": 1,
      "status": "PRESENT",
      "badge_color": "green",
      "distance": 15.2,
      "checkin_time": "10:12:05",
      "verified_by_admin": false
    },
    {
      "student_id": 2,
      "full_name": "Борисов Борис",
      "subgroup": 1,
      "status": "MANUAL_CONFIRM",
      "badge_color": "yellow",
      "distance": null,
      "checkin_time": null,
      "verified_by_admin": true,
      "note": "Разряжен аккумулятор"
    },
    {
      "student_id": 3,
      "full_name": "Волков Владимир",
      "subgroup": 1,
      "status": "ABSENT_EXCUSED",
      "badge_color": "purple",
      "excuse_reason": "Справка №421"
    }
  ]
}
```

### 5.2. `PATCH /attendance/override`
Ручное изменение статуса старостой (клик по фамилии или выбор причины).

- **Роли:** `STAROSTA`, `ZAM`
- **Request Body:**
```json
{
  "pair_id": 103,
  "student_id": 2,
  "new_status": "ABSENT_EXCUSED",
  "excuse_reason": "Заявление на имя декана от 08.09"
}
```
- **Response 200 OK:**
```json
{
  "success": true,
  "pair_id": 103,
  "student_id": 2,
  "status": "ABSENT_EXCUSED",
  "updated_at": "2026-09-08T10:25:10"
}
```

### 5.3. `POST /attendance/lock/{pair_id}`
Окончательное запирание журнала пары.

- **Роли:** `STAROSTA` (строго)
- **Response 200 OK:**
```json
{
  "success": true,
  "pair_id": 103,
  "is_locked": true,
  "locked_at": "2026-09-08T11:45:00"
}
```

---

## 6. Группа эндпоинтов: Экстренные оповещения и Отчетность

### 6.1. `POST /alerts/broadcast`
Отправка оповещения группе.

- **Роли:** `STAROSTA`, `ZAM`
- **Request Body:**
```json
{
  "type": "CRITICAL",
  "title": "Перенос пары",
  "body": "Пара по ОС перенесена в аудиторию 401 Корпуса А!"
}
```
- **Response 202 Accepted:**
```json
{
  "broadcast_id": 7,
  "queued_recipients": 28,
  "channel_posted": true,
  "status": "SENDING"
}
```

### 6.2. `POST /reports/export`
Формирование файла рапортички в Excel (`.xlsx`).

- **Роли:** `STAROSTA`, `ZAM`
- **Request Body:**
```json
{
  "date_from": "2026-09-01",
  "date_to": "2026-09-08",
  "delivery_method": "TELEGRAM_DM"
}
```
- **Response 200 OK:**
```json
{
  "file_name": "Рапортичка_240326_01.09-08.09.xlsx",
  "delivered_to_telegram": true,
  "total_pairs": 24,
  "total_absent_hours": 18
}
```
