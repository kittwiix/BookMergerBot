#!/bin/bash
set -e

echo "=== Установка BookMergerBot ==="

echo "1. Установка системных пакетов..."
apt-get update
apt-get install -y python3 python3-venv unrar unzip p7zip-full

echo "2. Создание виртуального окружения Python..."
python3 -m venv venv
source venv/bin/activate

echo "3. Установка Python библиотек..."
pip install aiogram rarfile python-dotenv lxml aiofiles

echo "4. Создание пустого .env файла..."
if [ ! -f ".env" ]; then
    echo "BOT_TOKEN=your_bot_token_here" > .env
    echo "Создан .env файл. ОТРЕДАКТИРУЙ ЕГО И УКАЖИ ТОКЕН!"
else
    echo ".env файл уже существует"
fi

echo "5. Создание временной директории..."
mkdir -p temp
chmod 777 temp

echo "6. Настройка systemd сервиса..."
cat > /etc/systemd/system/bookmergerbot.service << EOF
[Unit]
Description=BookMergerBot
After=network.target

[Service]
Type=simple
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable bookmergerbot

echo ""
echo "=== УСТАНОВКА ЗАВЕРШЕНА ==="
echo ""
echo "ВАЖНО: Настройте токен бота перед запуском!"
echo "1. Отредактируйте .env файл: nano .env"
echo "2. Замените 'your_bot_token_here' на реальный токен"
echo "3. Сохраните файл: Ctrl+X, Y, Enter"
echo ""
echo "Запуск бота: systemctl start bookmergerbot"
echo "Проверка статуса: systemctl status bookmergerbot"
echo "Просмотр логов: journalctl -u bookmergerbot -f"