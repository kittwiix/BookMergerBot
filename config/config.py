import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent 
env_path = BASE_DIR / '.env'

print(f"🔍 Загружаю .env из: {env_path}")
print(f"📁 Файл существует: {env_path.exists()}")

# Проверка кодировки файла .env (опционально, если установлен chardet)
if env_path.exists():
    try:
        import chardet
        with open(env_path, 'rb') as f:
            raw_data = f.read()
            detected = chardet.detect(raw_data)
            encoding = detected.get('encoding', 'unknown')
            confidence = detected.get('confidence', 0)
            
            if encoding and encoding.lower() not in ['utf-8', 'ascii'] and confidence > 0.7:
                print(f"⚠️  ВНИМАНИЕ: Файл .env обнаружен в кодировке {encoding} (уверенность: {confidence:.0%})")
                print(f"   Рекомендуется пересохранить файл в кодировке UTF-8")
            elif encoding and encoding.lower() in ['utf-8', 'ascii']:
                print(f"✅ Кодировка файла .env: {encoding}")
    except ImportError:
        # chardet не установлен, пропускаем проверку
        pass
    except Exception as e:
        print(f"⚠️  Не удалось определить кодировку файла .env: {e}")

try:
    load_dotenv(env_path, encoding='utf-8')
    print("✅ Файл .env загружен с кодировкой UTF-8")
except Exception as e1:
    try:
        print("⚠️  Попытка загрузить .env с кодировкой UTF-16...")
        load_dotenv(env_path, encoding='utf-16')
        print("✅ Файл .env загружен с кодировкой UTF-16")
    except Exception as e2:
        try:
            print("⚠️  Попытка загрузить .env с кодировкой UTF-8-sig...")
            load_dotenv(env_path, encoding='utf-8-sig')
            print("✅ Файл .env загружен с кодировкой UTF-8-sig")
        except Exception as e3:
            print(f"❌ Ошибка загрузки .env файла: {e3}")
            raise

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