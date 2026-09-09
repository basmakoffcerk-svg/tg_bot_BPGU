# 🎓 АРМ Старосты («Пульт управления группой 240326») — БГПУ им. М. Акмуллы

Полнофункциональный программный комплекс для академической группы **240326 «Матинф»** Института физики, математики, цифровых и нанотехнологий Башкирского государственного педагогического университета.

Включает в себя:
- **Telegram Bot (aiogram 3.x):** онбординг по предзагруженному вайтлисту, подтверждение старостой в 1 клик, рассылка экстренных алертов (@all + ЛС) и выдача ведомостей.
- **FastAPI REST API:** высокопроизводительный асинхронный сервер с криптографической аутентификацией `initData` по алгоритму HMAC-SHA256 и ролевым контролем (RBAC).
- **Telegram Mini App (TMA SPA):** мобильное веб-приложение (<50KB, 100/100 Lighthouse) с GPS-геочекином ($d \le 150$ м), обратным отсчетом окна отметки и интерактивной шахматкой старосты с быстрой сменой статусов.
- **Официальный генератор рапортичек (openpyxl):** автоматическая сборка ведомостей деканата установленного образца с еженедельным субботним триггером (APScheduler).
- **База данных SQLite (WAL Mode):** оптимизированные прагмы памяти (mmap, 64MB cache), устойчивость к взрывным нагрузкам одновременного чекина.

---

## 🚀 Быстрый запуск

### 1. Локальный запуск
```bash
# Клонирование и переход в проект
cd tg_bot

# Создание виртуального окружения и установка зависимостей
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env (укажите BOT_TOKEN, STAROSTA_TELEGRAM_ID)

# Первичный сидинг базы данных (группа 240326 и сетка БГПУ)
python data/seed_data.py

# Запуск единого процесса (FastAPI + aiogram Bot + Scheduler)
python main.py
```

### 2. Запуск в Docker Compose
```bash
docker-compose up -d --build
```

---

## 🧪 Запуск тестов
```bash
source .venv/bin/activate
pytest -v
```

---

## 📁 Структура проекта
```
tg_bot/
├── api/                       # REST API (FastAPI)
│   ├── routes/               # Эндпоинты (auth, schedule, attendance, alerts, reports, health)
│   ├── schemas/              # Pydantic v2 схемы данных
│   ├── dependencies.py       # RBAC Guards и валидация X-Telegram-Init-Data
│   └── app.py                # Конфигурация FastAPI и статики webapp
├── bot/                       # Telegram Bot (aiogram 3.x)
│   ├── handlers/             # Обработчики онбординга, команд и колбэков
│   ├── keyboards/            # Инлайн-клавиатуры выбора ФИО и меню WebApp
│   └── bot.py                # Инициализация Bot и Dispatcher
├── core/                      # Ядро приложения
│   ├── config.py             # Настройки Pydantic-Settings
│   ├── database.py           # SQLAlchemy 2.0 AsyncEngine + SQLite WAL
│   └── security.py           # HMAC-SHA256 валидация initData
├── models/                    # ORM модели (SQLAlchemy Declarative)
│   ├── user.py               # Student (студенты, роли, подгруппы)
│   ├── schedule.py           # Subject, ScheduleSlot, PairsRegistry
│   ├── attendance.py         # Attendance (журнал посещаемости)
│   └── audit.py              # AuditLog, BroadcastMessage
├── services/                  # Сервисный слой
│   ├── geo_service.py        # Двухфазный Geofencing (Bounding Box + Haversine)
│   ├── attendance_service.py # Чекин, шахматка, оверрайды, блокировка
│   ├── excel_generator.py    # Официальная ведомость деканата (.xlsx)
│   ├── broadcaster.py        # Token-bucket рассыльщик сообщений
│   └── scheduler.py          # APScheduler (автоотчет по субботам в 16:00)
├── webapp/                    # Фронтенд Telegram Mini App (HTML5 / CSS3 / Vanilla JS)
│   ├── index.html            # Каркас SPA
│   ├── css/styles.css        # Стили под тему Telegram
│   └── js/                   # Модули API, Geocheck, Grid, App
├── data/                      # Сидирование
│   └── seed_data.py          # Список группы 240326 и расписание корпусов БГПУ
├── tests/                     # Комплекс из 34 автоматических тестов (pytest)
├── Dockerfile                 # Multi-stage production образ
├── docker-compose.yml         # Контейнеризация с постоянным volume
├── requirements.txt           # Зависимости
└── main.py                    # Главная точка входа
```

---

## 🏛️ Корпуса БГПУ в системе
- **Корпус 2 (БГПУ им. Максима Танка):** г. Минск, ул. Советская, 18 (`lat: 53.893769, lon: 27.544440`)
- **Главный корпус:** г. Минск, пл. Независимости / ул. Советская, 18 (`lat: 53.894100, lon: 27.544600`)
- **Радиус фиксации:** 150 метров (GPS Accuracy $\le 50$ м).
