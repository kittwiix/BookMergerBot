import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    TEMP_DIR = "temp"
    bot: Optional[any] = None
    
    def __init__(self):
        if not self.BOT_TOKEN:
            raise ValueError("❌ Токен бота не найден!")
        Path(self.TEMP_DIR).mkdir(exist_ok=True)