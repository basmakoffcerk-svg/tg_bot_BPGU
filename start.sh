#!/data/data/com.termux/files/usr/bin/bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🚀 Запуск АРМ Старосты (Telegram Bot + Mini App Backend) в Termux..."
termux-wake-lock
proot-distro login debian -- /bin/bash -c "cd $DIR && source .venv_debian/bin/activate && PYTHONPATH=. python main.py"

