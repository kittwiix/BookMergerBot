import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

async def main():
    try:
        from config.config import Config
        from bot import router, bot_data
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        config = Config()
        bot_data.config = config
        
        bot = Bot(token=config.BOT_TOKEN)
        bot_data.config.bot = bot
        bot_data.bot_instance = bot
        
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        from archive_handler import ArchiveHandler
        from fb2_merger import FB2Merger
        
        bot_data.archive_handler = ArchiveHandler(use_file_storage=True)
        bot_data.merger = FB2Merger(max_memory_mb=2048)
        
        dp.include_router(router)
        
        print("🤖 BookMergeBot запущен!")
        print("📁 Отправляйте архивы с FB2")
        
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        sys.exit(1)

if __name__ == '__main__':
    env_path = PROJECT_ROOT / '.env'
    
    if not env_path.exists():
        print(f"❌ Файл .env не найден!")
        print(f"📁 Искал по пути: {env_path}")
        print("ℹ️  Создайте файл .env в корне проекта с содержанием:")
        print("BOT_TOKEN=ваш_токен")
        sys.exit(1)
    
    asyncio.run(main())