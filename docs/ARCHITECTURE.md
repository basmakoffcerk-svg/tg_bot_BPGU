# АРХИТЕКТУРА И СИСТЕМНЫЙ ДИЗАЙН (ARCHITECTURE)

## Проект: АРМ Старосты («Пульт управления группой 240326»)
**Версия:** 1.0.0  
**Технологический стек:** Python 3.11+, FastAPI, aiogram 3.x, SQLAlchemy 2.0 (asyncio), SQLite, openpyxl, APScheduler, Telegram WebApp SDK.

---

## 1. Концептуальная архитектура (C4 Container)

Система построена по модели асинхронного модульного монолита, где Telegram-бот и REST API работают в едином процессе под управлением ASGI-сервера Uvicorn.

```mermaid
C4Container
    title Диаграмма контейнеров системы АРМ Старосты

    Person(student, "Студент", "Член группы 240326. Смотрит расписание, чекинится по GPS")
    Person(starosta, "Староста / Зам", "Управляет группой, модерирует посещаемость, шлет алерты")

    System_Boundary(c1, "Экосистема Telegram") {
        Container(tg_client, "Telegram Client (iOS/Android/Desktop)", "Официальный клиент Telegram")
        Container(tma_ui, "Telegram Mini App (TMA)", "HTML5, CSS3, Vanilla JS, TMA SDK", "Встроенное веб-приложение: карточки пар, шахматка, GPS")
    }

    System_Boundary(backend_boundary, "Серверный бэкенд (Python 3.11+)") {
        Container(fastapi_app, "FastAPI Web Server", "Python, FastAPI, Pydantic v2", "Обработка REST API, валидация initData, выдача данных TMA")
        Container(aiogram_bot, "Telegram Bot Engine", "aiogram 3.x", "Обработка команд (/start), онбординг, push-уведомления")
        Container(geo_engine, "Модуль геовалидации", "Haversine formula", "Вычисление расстояний, фильтрация accuracy")
        Container(report_gen, "Генератор ведомостей", "openpyxl / ReportLab", "Формирование официальных рапортичек .xlsx")
        Container(scheduler, "Фоновый планировщик", "APScheduler (AsyncIO)", "Субботняя автовыгрузка отчетов, напоминания о парах")
    }

    ContainerDb(sqlite_db, "База данных", "SQLite (aiosqlite + SQLAlchemy)", "Студенты, расписание, журнал посещаемости, аудит-лог")
    System_Ext(telegram_api, "Telegram Bot API", "HTTPS REST API Telegram для рассылки сообщений")

    Rel(student, tg_client, "Взаимодействует")
    Rel(starosta, tg_client, "Взаимодействует")
    Rel(tg_client, tma_ui, "Открывает через кнопку WebApp")
    Rel(tma_ui, fastapi_app, "REST API запросы (X-Telegram-Init-Data)", "HTTPS / JSON")
    Rel(tg_client, telegram_api, "Команды и клики")
    Rel(telegram_api, aiogram_bot, "Webhooks / Long Polling")
    Rel(aiogram_bot, telegram_api, "Отправка алертов и файлов рапортичек")
    Rel(fastapi_app, geo_engine, "Координаты студента и аудитории")
    Rel(fastapi_app, sqlite_db, "Чтение/запись данных", "Async SQLAlchemy")
    Rel(aiogram_bot, sqlite_db, "Чтение/запись пользователей", "Async SQLAlchemy")
    Rel(scheduler, report_gen, "Триггер по расписанию")
    Rel(report_gen, sqlite_db, "Выборка за неделю")
```

---

## 2. Диаграммы последовательности ключевых процессов

### 2.1. Аутентификация и валидация Telegram `initData` (HMAC-SHA256)
Вся авторизация в Mini App происходит без передачи логинов и паролей на базе криптографической подписи Telegram:

```mermaid
sequenceDiagram
    autonumber
    actor Student as Студент
    participant TMA as Mini App (Фронтенд)
    participant API as FastAPI (Бэкенд)
    participant DB as База данных (SQLite)

    Student->>TMA: Открытие Mini App из меню Telegram
    TMA->>TMA: Чтение window.Telegram.WebApp.initData
    TMA->>API: POST /api/v1/auth/telegram (Header: X-Telegram-Init-Data)
    
    rect rgb(240, 248, 255)
        Note over API: 1. Парсинг query-string<br/>2. Извлечение hash<br/>3. HMAC-SHA256(bot_token, "WebAppData") = secret_key<br/>4. HMAC-SHA256(data_check_string, secret_key) == hash<br/>5. Проверка auth_date (свежесть <= 86400 сек)
    end

    alt Подпись не совпадает или просрочена
        API-->>TMA: 401 Unauthorized ("Invalid cryptographic signature")
    else Подпись валидна
        API->>DB: Поиск студента по telegram_id
        DB-->>API: Данные студента (ID, ФИО, подгруппа, роль: STUDENT/STAROSTA)
        API-->>TMA: 200 OK (JWT/Session Token + UserProfile + Permissions)
    end
```

### 2.2. Процесс геочекина на занятии
```mermaid
sequenceDiagram
    autonumber
    actor Student as Студент
    participant TMA as Mini App
    participant Geolocation as HTML5 Geolocation API
    participant API as FastAPI Backend
    participant GeoEngine as Haversine Engine
    participant DB as SQLite DB
    participant Bot as aiogram Bot

    Student->>TMA: Нажатие кнопки «Отметиться на паре»
    TMA->>Geolocation: getCurrentPosition(enableHighAccuracy: true)
    Geolocation-->>TMA: Coordinates (lat, lon, accuracy)
    
    alt accuracy > 50 метров
        TMA-->>Student: Ошибка: Сигнал GPS неточен (> 50м). Выйдите к окну.
    else accuracy <= 50 метров
        TMA->>API: POST /api/v1/attendance/checkin {pair_id, lat, lon, accuracy}
        API->>DB: Запрос координат корпуса и времени пары
        DB-->>API: Пары (time_start, time_end, building_lat, building_lon)
        
        rect rgb(255, 250, 240)
            Note over API: Проверка временного окна:<br/>[time_start - 5 мин ... time_start + 15 мин]
        end

        API->>GeoEngine: calculate_distance((lat, lon), (building_lat, building_lon))
        GeoEngine-->>API: Distance d (в метрах)

        alt d <= 150 метров
            API->>DB: INSERT INTO attendance (status='PRESENT', distance=d, geo_verified=1)
            API-->>TMA: 200 OK {status: "CHECKED_IN", distance: d}
            TMA-->>Student: 🟢 Вы успешно отметились! (Дистанция: d м)
        else d > 150 метров
            API-->>TMA: 400 Bad Request {error: "OUT_OF_BOUNDS", distance: d}
            TMA-->>Student: 🔴 Вы находитесь вне аудитории (дистанция: d м)
        end
    end
```

### 2.3. Интерактивная шахматка старосты и оверрайды
```mermaid
sequenceDiagram
    autonumber
    actor Starosta as Староста
    participant TMA as Mini App (Панель старосты)
    participant API as FastAPI
    participant DB as SQLite
    participant Audit as Audit Logger

    Starosta->>TMA: Открытие вкладки «Шахматка текущей пары»
    TMA->>API: GET /api/v1/attendance/grid/{pair_id}
    API->>DB: SELECT students + attendance_records
    DB-->>API: Сетка 25-30 студентов со статусами
    API-->>TMA: 200 OK (JSON Grid)
    
    Starosta->>TMA: Одиночный тап по студенту "Иванов И." (был СЕРЫЙ)
    TMA->>API: PATCH /api/v1/attendance/override {student_id, pair_id, new_status: "MANUAL_CONFIRM"}
    API->>DB: UPDATE attendance SET status='MANUAL_CONFIRM', verified_by_admin=1
    API->>Audit: INSERT INTO audit_log (admin_id, action, target_student_id)
    API-->>TMA: 200 OK (Новый статус подтвержден)
    TMA-->>Starosta: Карточка окрашивается в ЖЕЛТЫЙ 🟡
    
    Starosta->>TMA: Нажатие кнопки «Зафиксировать пару»
    TMA->>API: POST /api/v1/attendance/lock/{pair_id}
    API->>DB: UPDATE pairs SET is_locked=1, locked_at=NOW()
    API-->>TMA: 200 OK {locked: true}
    TMA-->>Starosta: Панель переходит в режим архива (чекин закрыт)
```

---

## 3. Архитектура безопасности

### 3.1. Алгоритм валидации `initData` на Python
```python
import hmac
import hashlib
from urllib.parse import parse_qsl

def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """
    Валидация подлинности данных запуска WebApp по спецификации Telegram.
    1. Парсим строку вида key=value&hash=...
    2. Извлекаем переданный hash
    3. Формируем data_check_string из остальных параметров по алфавиту
    4. Вычисляем secret_key = HMAC_SHA256("WebAppData", bot_token)
    5. Вычисляем hmac = HMAC_SHA256(secret_key, data_check_string).hexdigest()
    6. Сравниваем hmac с hash
    """
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    # Сортировка параметров по ключам
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    
    # Генерация секретного ключа
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    
    # Вычисление контрольного хэша
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    
    if hmac.compare_digest(calculated_hash, received_hash):
        return parsed
    return None
```

### 3.2. Ролевой Middleware и Dependency Injection
В FastAPI эндпоинты защищены цепочкой зависимостей:
```python
async def get_current_user(x_telegram_init_data: str = Header(...)) -> User:
    user_data = validate_telegram_init_data(x_telegram_init_data, settings.BOT_TOKEN)
    if not user_data:
        raise HTTPException(status_code=401, detail="Invalid Telegram InitData")
    # Проверка в БД и возврат User
    ...

def require_roles(*allowed_roles: RoleEnum):
    async def role_checker(user: User = Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Forbidden: Insufficient permissions")
        return user
    return role_checker
```

---

## 4. Структура кодовой базы проекта

```
tg_bot/
├── bot/                       # Слой Telegram-бота (aiogram 3.x)
│   ├── handlers/             # Обработчики команд (/start, /help, /report)
│   ├── keyboards/            # Инлайн и реплай клавиатуры
│   ├── middlewares/          # Мидлвари (троттлинг, регистрация пользователей)
│   └── bot.py                # Инициализация Bot и Dispatcher
├── api/                       # Слой REST API (FastAPI)
│   ├── routes/               # Эндпоинты (auth, schedule, attendance, reports, alerts)
│   ├── schemas/              # Pydantic v2 схемы запросов/ответов
│   ├── dependencies.py       # Авторизация initData и RBAC guards
│   └── app.py                # Инициализация FastAPI приложения
├── core/                      # Ядро приложения
│   ├── config.py             # Настройки (pydantic-settings, .env)
│   ├── security.py           # HMAC валидация, криптография
│   └── database.py           # Подключение SQLAlchemy 2.0 AsyncEngine
├── models/                    # Декларативные ORM модели (SQLAlchemy)
│   ├── user.py               # Пользователи и студенты
│   ├── schedule.py           # Расписание и аудитории
│   ├── attendance.py         # Записи посещаемости
│   └── audit.py              # Журнал действий старосты
├── services/                  # Бизнес-логика
│   ├── geo_service.py        # Расчет расстояния (Haversine) и точности
│   ├── attendance_service.py # Чекин, шахматка, оверрайды
│   ├── excel_generator.py    # Сборка ведомости openpyxl
│   ├── broadcaster.py        # Рассылка экстренных алертов (@all, ЛС)
│   └── scheduler.py          # Планировщик фоновых задач APScheduler
├── webapp/                    # Фронтенд Telegram Mini App (SPA)
│   ├── index.html            # Каркас приложения
│   ├── css/                  # Стили (мобильная верстка, Telegram theme vars)
│   ├── js/                   # Логика: Geolocation, API client, шахматка
│   └── assets/               # Иконки и статика
├── docs/                      # Проектная документация (SRS, ARCHITECTURE, DB, API, DEPLOY)
├── tests/                     # Автоматические тесты (pytest, pytest-asyncio)
├── alembic/                   # Миграции базы данных
├── main.py                    # Главная точка входа (запуск FastAPI + aiogram webhook/polling)
├── requirements.txt           # Зависимости Python
├── Dockerfile                 # Докеризация сервиса
└── docker-compose.yml         # Оркестрация контейнеров
```
