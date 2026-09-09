#!/data/data/com.termux/files/usr/bin/bash
echo "🌐 Запуск бесплатного HTTPS-туннеля для Telegram Mini App..."
echo "Скопируйте появившуюся https:// ссылку и укажите её в Telegram BotFather:"
ssh -R 80:localhost:8000 nokey@localhost.run
