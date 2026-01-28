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

echo "4. Проверка .env файла..."
if [ ! -f ".env" ]; then
    echo "ОШИБКА: .env файл не найден в корне проекта!"
    echo "Создайте файл .env в корне с BOT_TOKEN=ваш_токен"
    exit 1
fi

echo "5. Проверка содержимого .env файла..."
if ! grep -q "BOT_TOKEN=" .env; then
    echo "ОШИБКА: В .env файле нет BOT_TOKEN!"
    echo "Отредактируйте .env файл:"
    echo "nano .env"
    echo "Добавьте строку: BOT_TOKEN=ваш_токен"
    exit 1
fi

echo "6. Проверка кодировки .env файла..."
file -b .env | grep -q "UTF-8" || echo "ВНИМАНИЕ: .env файл не в UTF-8. Пересохраните в UTF-8:"
echo "  nano .env"
echo "  Ctrl+O, Enter, Ctrl+X"

echo "7. Создание временной директории..."
mkdir -p temp
chmod 777 temp

echo "8. Настройка systemd сервиса..."
SERVICE_FILE="/etc/systemd/system/bookmergerbot.service"
WORK_DIR=$(pwd)

cat > $SERVICE_FILE << EOF
[Unit]
Description=BookMergerBot Telegram Bot
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$WORK_DIR
Environment="PATH=$WORK_DIR/venv/bin"
ExecStart=$WORK_DIR/venv/bin/python $WORK_DIR/main.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

chmod 644 $SERVICE_FILE
systemctl daemon-reload
systemctl enable bookmergerbot

echo ""
echo "=== УСТАНОВКА ЗАВЕРШЕНА ==="
echo ""
echo "Структура проекта:"
echo "  .env              - файл с токеном бота (уже создан)"
echo "  main.py           - точка входа"
echo "  config/config.py  - конфигурация"
echo "  src/              - исходный код"
echo ""
echo "Токен бота:"
grep "BOT_TOKEN" .env | head -1
echo ""
echo "Команды управления:"
echo "  Запуск:      sudo systemctl start bookmergerbot"
echo "  Остановка:   sudo systemctl stop bookmergerbot"
echo "  Статус:      sudo systemctl status bookmergerbot"
echo "  Логи:        sudo journalctl -u bookmergerbot -f"
echo ""
echo "Для запуска вручную:"
echo "  source venv/bin/activate"
echo "  python main.py"
echo ""
echo "Важно: Убедитесь, что .env файл в кодировке UTF-8!"