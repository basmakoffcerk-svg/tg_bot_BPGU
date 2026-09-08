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
echo "[1/4] Установка системных утилит..."
pkg update -y && pkg upgrade -y
pkg install -y python git clang libffi openssl openssh curl jq

# 3. Клонирование / обновление репозитория
echo "[2/4] Загрузка проекта..."
cd ~
if [ -d "tg_bot_BPGU" ]; then
    cd tg_bot_BPGU
    git pull origin main
else
    git clone https://github.com/basmakoffcerk-svg/tg_bot_BPGU.git
    cd tg_bot_BPGU
fi

# 4. Виртуальное окружение и зависимости
echo "[3/4] Установка библиотек (aiogram, fastapi, sqlalchemy)..."
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 5. Проверка директории данных
mkdir -p data/backups

echo "[4/4] Запуск SSH-сервера для удаленного управления..."
sshd
IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
echo "=========================================="
echo "✅ УСТАНОВКА ЗАВЕРШЕНА!"
echo "IP вашего телефона в Wi-Fi сети: $IP"
echo "Порт SSH: 8022"
echo "Пользователь Termux: $(whoami)"
echo "=========================================="
echo ""
echo "🚀 Запуск комплекса АРМ Старосты..."
python main.py
