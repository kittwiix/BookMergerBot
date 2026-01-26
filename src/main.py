import asyncio
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        from config.config import Config
        from bot import router, bot_data
        from aiogram import Bot, Dispatcher
        from aiogram.fsm.storage.memory import MemoryStorage
        
        bot_data.config = Config()
        
        bot = Bot(token=bot_data.config.BOT_TOKEN)
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
    if not Path('.env').exists():
        print("❌ Создайте файл .env с BOT_TOKEN=ваш_токен")
        sys.exit(1)
    
    asyncio.run(main())