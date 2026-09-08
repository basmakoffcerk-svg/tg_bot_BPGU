#!/data/data/com.termux/files/usr/bin/bash
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo "🚀 Запуск АРМ Старосты (Telegram Bot + Mini App Backend)..."
python main.py
