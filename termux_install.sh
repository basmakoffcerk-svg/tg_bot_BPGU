#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "=== [1/4] Обновление пакетов Termux ==="
pkg update -y && pkg upgrade -y

echo "=== [2/4] Установка Python, Git, OpenSSH, компиляторов ==="
pkg install -y python git clang libffi openssl openssh

echo "=== [3/4] Создание виртуального окружения ==="
python -m venv .venv
source .venv/bin/activate

echo "=== [4/4] Установка Python-зависимостей ==="
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "✅ Установка успешно завершена!"
echo "Для запуска бота введите:"
echo "bash start.sh"
