#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=========================================="
echo "   АРМ СТАРОСТЫ — АВТОМАТИЧЕСКАЯ УСТАНОВКА"
echo "=========================================="

# 1. Защита от засыпания
if command -v termux-wake-lock &> /dev/null; then
    termux-wake-lock
    echo "[✓] WakeLock активирован (Android не усыпит процесс)"
fi

# 2. Обновление и установка необходимых пакетов
echo "[1/4] Установка системных пакетов Termux..."
pkg update -y && pkg upgrade -y
pkg install -y python git clang libffi openssl openssh curl jq

# 3. Клонирование / обновление репозитория
echo "[2/4] Загрузка / обновление проекта..."
cd ~
if [ -d "tg_bot_BPGU" ]; then
    cd tg_bot_BPGU
    git pull origin main || true
elif [ -d "tg_bot" ]; then
    cd tg_bot
    git pull origin main || true
else
    git clone https://github.com/basmakoffcerk-svg/tg_bot_BPGU.git
    cd tg_bot_BPGU
fi

# 4. Виртуальное окружение и зависимости
echo "[3/4] Сборка окружения Python и установка зависимостей..."
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Инициализация базы данных
mkdir -p data/backups
if [ ! -f "data/database.sqlite" ]; then
    echo "[*] Инициализация эталонной базы данных (студенты, слоты, БГПУ Корпус 2)..."
    python data/seed_data.py || true
fi

# 6. Конфигурация .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[!] Создан файл .env из шаблона. Укажите в нем свой BOT_TOKEN."
    fi
fi

echo "=========================================="
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
echo "IP телефона в локальной сети: $IP"
echo "Локальный порт API: 8000"
echo "=========================================="
echo ""
echo "🚀 Запуск АРМ Старосты..."
python main.py
