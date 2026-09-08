#!/data/data/com.termux/files/usr/bin/bash
echo "🌐 Запуск защищенного HTTPS-туннеля для Mini App..."
echo "Скопируйте полученную https:// ссылку для меню бота:"
ssh -R 80:localhost:8000 nokey@localhost.run
