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

echo "4. Создание временной директории..."
mkdir -p temp
chmod 777 temp

echo "5. Настройка systemd сервиса..."
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
echo "Запуск бота: systemctl start bookmergerbot"
echo "Проверка статуса: systemctl status bookmergerbot"
echo "Просмотр логов: journalctl -u bookmergerbot -f"
echo ""
echo "Файл .env уже настроен с токеном."