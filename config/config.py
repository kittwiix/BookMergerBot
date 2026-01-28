import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent 
env_path = BASE_DIR / '.env'

print(f"🔍 Загружаю .env из: {env_path}")
print(f"📁 Файл существует: {env_path.exists()}")

try:
    load_dotenv(env_path, encoding='utf-8')
except:
    try:
        load_dotenv(env_path, encoding='utf-16')
    except:
        load_dotenv(env_path, encoding='utf-8-sig')

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    TEMP_DIR = BASE_DIR / "temp" 
    
    @classmethod
    def validate(cls):
        print(f"🔑 Получен токен: {'ДА' if cls.BOT_TOKEN else 'НЕТ'}")
        print(f"📏 Длина токена: {len(cls.BOT_TOKEN) if cls.BOT_TOKEN else 0}")
        
        if not cls.BOT_TOKEN:
            raise ValueError(f"""
❌ Токен бота не найден!

Проверь:
- Файл должен быть в: {env_path}
- Содержимое: BOT_TOKEN=твой_токен
- Кодировка файла: UTF-8 (без BOM)
""")
        
        cls.TEMP_DIR.mkdir(exist_ok=True)
        print(f"✅ Temp папка: {cls.TEMP_DIR}")
        print("✅ Конфигурация загружена успешно!")

Config.validate()