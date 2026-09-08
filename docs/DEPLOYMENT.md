# РУКОВОДСТВО ПО РАЗВЕРТЫВАНИЮ И ЭКСПЛУАТАЦИИ (DEPLOYMENT)

## Проект: АРМ Старосты («Пульт управления группой 240326»)
**Архитектура:** Hybrid Serverless Frontend (TMA) + Containerized Async Backend (FastAPI + aiogram 3.x)

---

## 1. Топология развертывания

```
   ┌─────────────────────────────────────────────────────────────┐
   │                  Telegram BotFather API                     │
   └──────────────┬───────────────────────────────┬──────────────┘
                  │ Webhook (HTTPS)               │ Menu Button URL
                  ▼                               ▼
   ┌──────────────────────────────┐┌─────────────────────────────┐
   │    Backend Сервер            ││    Frontend Mini App        │
   │    (FastAPI + aiogram)       ││    (HTML5 / JS / CSS)       │
   │                              ││                             │
   │ • Хостинг: Amvera / VPS      ││ • Хостинг: Vercel / GitHub  │
   │ • Домен: api.starosta.app    ││ • Домен: app.starosta.app   │
   │ • База: SQLite (WAL-volume)  ││ • Бесплатный SSL (HTTPS)    │
   └──────────────────────────────┘└─────────────────────────────┘
```

---

## 2. Бесплатные и низкобюджетные платформы

| Компонент | Рекомендуемый сервис | Альтернатива | Стоимость | Особенности |
| :--- | :--- | :--- | :--- | :--- |
| **Frontend (TMA)** | **Vercel** | GitHub Pages / Cloudflare Pages | 0 ₽ / мес | Мгновенный деплой из Git, встроенный бесплатный SSL (обязателен для Geolocation API). |
| **Backend (Бот + API)** | **Amvera Cloud** | Домашний Mini PC / Ubuntu VPS | 0–150 ₽ / мес (грант) | Российские дата-центры, нет блокировок Telegram API, поддержка постоянных дисков (Persistent Volume для SQLite). |

---

## 3. Регистрация и настройка Telegram-бота

### 3.1. Создание бота через [@BotFather](https://t.me/BotFather)
1. Отправьте команду `/newbot`.
2. Введите имя: `Пульт Старосты 240326`.
3. Введите username: например, `starosta_240326_bot`.
4. Сохраните выданный токен `BOT_TOKEN`.

### 3.2. Настройка кнопки запуска Mini App (Menu Button)
1. В диалоге с BotFather выполните команду `/setmenubutton`.
2. Выберите созданного бота.
3. Введите URL фронтенда: `https://app.starosta.app` (или URL на Vercel).
4. Укажите текст кнопки: `📱 Открыть пульт`.

### 3.3. Настройка команд бота
Отправьте BotFather команду `/setcommands`:
```text
start - Открыть главное меню и зарегистрироваться
status - Моя посещаемость и текущая пара
report - Запросить рапортичку (для старосты)
help - Инструкция и помощь
```

---

## 4. Конфигурация окружения (`.env`)

Создайте файл `.env` в корне проекта:

```ini
# ==========================================
# ОСНОВНЫЕ НАСТРОЙКИ TELEGRAM
# ==========================================
BOT_TOKEN=7123456789:AAHfdjsdhfkjsdfhkjsdfhksjdfhksjdfh
STAROSTA_TELEGRAM_ID=123456789
GROUP_CHAT_ID=-1001234567890

# ==========================================
# СЕРВЕР И СЕТЬ
# ==========================================
HOST=0.0.0.0
PORT=8000
APP_ENV=production
TIMEZONE=Europe/Moscow

# URL вебхука бота (если используется Webhook вместо Polling)
WEBHOOK_URL=https://api.starosta.app/webhook
WEBHOOK_SECRET=your_super_secret_webhook_token_here

# URL фронтенда Mini App (для CORS)
FRONTEND_URL=https://app.starosta.app

# ==========================================
# БАЗА ДАННЫХ И ХРАНИЛИЩЕ
# ==========================================
DATABASE_URL=sqlite+aiosqlite:///data/database.sqlite
BACKUP_DIR=data/backups

# ==========================================
# ПАРАМЕТРЫ ГЕОЧЕКИНА
# ==========================================
MAX_ALLOWED_DISTANCE_METERS=150
MAX_GPS_ACCURACY_METERS=50
CHECKIN_WINDOW_BEFORE_MINUTES=5
CHECKIN_WINDOW_AFTER_MINUTES=15
```

---

## 5. Запуск в Docker и Docker Compose

### 5.1. `Dockerfile` бэкенда
```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для сборки и SQLite
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    sqlite3 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Настройка часового пояса
ENV TZ=Europe/Moscow
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Установка зависимостей Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY . .

# Создание директории данных
RUN mkdir -p /app/data /app/data/backups

EXPOSE 8000

CMD ["python", "main.py"]
```

### 5.2. `docker-compose.yml`
```yaml
version: '3.8'

services:
  backend:
    build: .
    container_name: starosta_backend
    restart: unless-stopped
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./data:/app/data
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
```

---

## 6. Локальная разработка и отладка (с пробросом портов)

Так как Telegram Mini App и Webhooks требуют действующий HTTPS-сертификат, для локальной разработки используется утилита **ngrok** или **localtunnel**:

1. Запустите виртуальное окружение:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Запустите сервер локально:
   ```bash
   uvicorn api.app:app --reload --port 8000
   ```
3. В отдельном терминале пробросьте порт:
   ```bash
   ngrok http 8000
   ```
4. Полученный HTTPS URL (например, `https://abc-123.ngrok-free.app`):
   - Укажите в BotFather как Menu Button URL (для отладки TMA).
   - Зарегистрируйте как Webhook бота:
     ```bash
     curl -F "url=https://abc-123.ngrok-free.app/webhook" https://api.telegram.org/bot<BOT_TOKEN>/setWebhook
     ```

---

## 7. Мониторинг и проверка жизнеспособности

Эндпоинт `/api/v1/health` возвращает статус состояния сервиса:
```json
{
  "status": "healthy",
  "database": "connected",
  "telegram_bot": "active",
  "server_time": "2026-09-08T18:00:00+03:00"
}
```
При сбоях в журнал выводится трассировка с ротацией логов `logs/app.log` (размер 10 МБ, хранение 5 ротаций).
