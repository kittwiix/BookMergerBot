import logging
import os
import shutil
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from asyncio import Lock
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, 
    FSInputFile, CallbackQuery, ReplyKeyboardMarkup, 
    KeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = Router()

class BookStates(StatesGroup):
    sorting = State()
    naming = State()

@dataclass
class BotData:
    sessions: Dict[int, 'UserSession'] = field(default_factory=dict)
    archive_handler: Optional['ArchiveHandler'] = None
    merger: Optional['FB2Merger'] = None
    config: Optional['Config'] = None
    bot_instance: Optional[Bot] = None
    user_locks: Dict[int, Lock] = field(default_factory=dict)

bot_data = BotData()

def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="📚 Слить книги"),
            KeyboardButton(text="📝 Сортировать книги")
        ],
        [
            KeyboardButton(text="✏️ Назвать сборник"),
            KeyboardButton(text="ℹ️ Справка")
        ],
        [
            KeyboardButton(text="🗑️ Очистить сессию"),
            KeyboardButton(text="📋 Список книг")
        ]
    ]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или отправьте файл"
    )

def get_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [[KeyboardButton(text="❌ Отмена")]]
    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
        one_time_keyboard=True
    )

def get_main_inline_keyboard():
    keyboard = [
        [
            InlineKeyboardButton(text="📚 Слить книги", callback_data="merge_books"),
            InlineKeyboardButton(text="📝 Сортировать книги", callback_data="sort_books")
        ],
        [
            InlineKeyboardButton(text="✏️ Назвать сборник", callback_data="name_collection"),
            InlineKeyboardButton(text="ℹ️ Справка", callback_data="show_help")
        ],
        [
            InlineKeyboardButton(text="🗑️ Очистить сессию", callback_data="clear_session")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_status_message(session: 'UserSession') -> str:
    books_count = len(session.book_contents)
    
    if books_count == 0:
        return "📚 Нет загруженных книг\n\n📥 Отправьте архив (ZIP/RAR) с FB2 файлами или отдельные FB2 файлы."
    
    sorted_books = session.get_sorted_books()
    books_list = "\n".join([f"{i+1}. {book.title}" for i, book in enumerate(sorted_books)])
    
    series_title = session.get_series_title()
    memory_usage = session.get_memory_usage() // (1024*1024) if books_count > 0 else 0
    
    return f"""📚 Загружено {books_count} книг
💾 Память: ~{memory_usage} MB
📖 Название сборника: {series_title}

📋 Книги в сборнике:
{books_list}

⚙️ Используйте кнопки ниже для управления:"""

async def create_status_message_at_bottom(chat_id: int, session: 'UserSession') -> bool:
    try:
        bot = bot_data.bot_instance
        if not bot:
            return False

        if session.status_message_id:
            try:
                await bot.delete_message(
                    chat_id=chat_id,
                    message_id=session.status_message_id
                )
            except Exception:
                pass
            finally:
                session.status_message_id = None

        status_text = create_status_message(session)
        
        msg = await bot.send_message(
            chat_id=chat_id,
            text=status_text,
            reply_markup=get_main_inline_keyboard()
        )
        session.status_message_id = msg.message_id
        return True
        
    except Exception:
        session.status_message_id = None
        return False

async def update_or_create_status(chat_id: int, session: 'UserSession', force_new: bool = False) -> bool:
    try:
        bot = bot_data.bot_instance
        if not bot:
            return False
            
        if len(session.book_contents) == 0:
            if session.status_message_id:
                try:
                    await bot.delete_message(
                        chat_id=chat_id,
                        message_id=session.status_message_id
                    )
                except Exception:
                    pass
                finally:
                    session.status_message_id = None
            return True

        if force_new or not session.status_message_id:
            return await create_status_message_at_bottom(chat_id, session)

        try:
            status_text = create_status_message(session)
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=session.status_message_id,
                text=status_text,
                reply_markup=get_main_inline_keyboard()
            )
            return True
            
        except Exception:
            return await create_status_message_at_bottom(chat_id, session)
                
    except Exception:
        session.status_message_id = None
        return False

def get_or_create_session(user_id: int) -> 'UserSession':
    if user_id not in bot_data.sessions:
        from src.models import UserSession
        bot_data.sessions[user_id] = UserSession(user_id=user_id)
    
    return bot_data.sessions[user_id]

def get_or_create_lock(user_id: int) -> Lock:
    if user_id not in bot_data.user_locks:
        bot_data.user_locks[user_id] = Lock()
    
    return bot_data.user_locks[user_id]

def cleanup_user_session(user_id: int):
    if user_id in bot_data.sessions:
        session = bot_data.sessions[user_id]

        for temp_dir in session.temp_dirs:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)

        del bot_data.sessions[user_id]

    user_dir = Path(bot_data.config.TEMP_DIR) / str(user_id)
    if user_dir.exists():
        shutil.rmtree(user_dir, ignore_errors=True)

    if user_id in bot_data.user_locks:
        del bot_data.user_locks[user_id]

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = None
        if user_id in bot_data.sessions:
            session = bot_data.sessions[user_id]

        if session and session.status_message_id:
            try:
                await bot_data.bot_instance.delete_message(
                    chat_id=chat_id,
                    message_id=session.status_message_id
                )
            except Exception:
                pass

        cleanup_user_session(user_id)

        session = get_or_create_session(user_id)
        
        welcome_text = """🤖 BookMergeBot

Отправляйте архивы (ZIP/RAR) с FB2 файлами.
После загрузки первого файла появится статусное сообщение

Поддерживаемые форматы:
- ZIP архивы с FB2
- RAR архивы с FB2  
- Отдельные FB2 файлы

Команды:
/start - Начало работы (очистить всё)
/help - Помощь
/clear - Очистить сессию"""
        
        await message.answer(
            welcome_text, 
            reply_markup=get_main_reply_keyboard()
        )

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = """📖 Помощь

1. Отправьте архив с FB2 файлами
2. Статусное сообщение появится под файлами
3. Используйте кнопки под сообщением для управления

Доступные действия:
📚 Слить книги - объединить все книги в один FB2
📝 Сортировать книги - изменить порядок книг
✏️ Назвать сборник - задать название для сборника
📋 Список книг - показать все загруженные книги
🗑️ Очистить сессию - удалить все загруженные книги"""
    
    await message.answer(
        help_text, 
        reply_markup=get_main_reply_keyboard()
    )

@router.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = None
        if user_id in bot_data.sessions:
            session = bot_data.sessions[user_id]

        if session and session.status_message_id:
            try:
                await bot_data.bot_instance.delete_message(
                    chat_id=chat_id,
                    message_id=session.status_message_id
                )
            except Exception:
                pass

        cleanup_user_session(user_id)

        session = get_or_create_session(user_id)

        await message.answer(
            "✅ Сессия очищена. Статусное сообщение удалено.",
            reply_markup=get_main_reply_keyboard()
        )

@router.message(Command("list"))
async def cmd_list(message: Message):
    user_id = message.from_user.id

    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if not session.book_contents:
            await message.answer("📭 Нет загруженных книг.")
            return
        
        books_list = "\n".join([f"{i+1}. {book.title}" for i, book in enumerate(session.book_contents)])
        response = f"📚 Загружено книг: {len(session.book_contents)}\n\n{books_list}"
        
        await message.answer(
            response,
            reply_markup=get_main_reply_keyboard()
        )

@router.message(F.text == "📚 Слить книги")
async def handle_merge_reply(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if len(session.book_contents) < 2:
            await message.answer(
                "❌ Нужно как минимум 2 книги для слияния.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        try:
            processing_msg = await message.answer("🔄 Начинаю слияние книг...")
            
            sorted_books = session.get_sorted_books()
            series_title = session.get_series_title()
            
            safe_title = "".join(c for c in series_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            output_filename = f"{safe_title}.fb2"
            output_path = Path(bot_data.config.TEMP_DIR) / str(user_id) / output_filename
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            success = await asyncio.get_event_loop().run_in_executor(
                None,
                bot_data.merger.create_merged_fb2,
                sorted_books,
                str(output_path),
                series_title
            )
            
            await processing_msg.delete()
            
            if success and output_path.exists():
                document = FSInputFile(output_path, filename=output_filename)
                await message.answer_document(
                    document,
                    caption=f"📚 {series_title}\nОбъединено книг: {len(sorted_books)}"
                )

                output_path.unlink()

                await update_or_create_status(chat_id, session)
                
            else:
                await message.answer(
                    "❌ Ошибка при создании файла.",
                    reply_markup=get_main_reply_keyboard()
                )
            
        except Exception as e:
            await message.answer(
                f"❌ Ошибка: {str(e)}",
                reply_markup=get_main_reply_keyboard()
            )

@router.message(F.text == "📝 Сортировать книги")
async def handle_sort_reply(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if not session.book_contents:
            await message.answer(
                "❌ Нет книг для сортировки.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        if len(session.book_contents) == 1:
            await message.answer(
                "ℹ️ Всего одна книга, сортировка не требуется.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        books_list = "\n".join([f"{i+1}. {b.title}" for i, b in enumerate(session.book_contents)])
        
        await state.set_state(BookStates.sorting)
        
        await message.answer(
            f"📚 Текущий порядок:\n\n{books_list}\n\n"
            f"Введите новый порядок цифрами через пробел:\n"
            f"Пример: 2 1 3 или 3 2 1\n\n"
            f"ℹ️ Введите номера книг в нужном порядке",
            reply_markup=get_cancel_reply_keyboard()
        )

@router.message(F.text == "✏️ Назвать сборник")
async def handle_name_reply(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if not session.book_contents:
            await message.answer(
                "❌ Нет книг для сборника.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        current_title = session.get_series_title()
        
        await state.set_state(BookStates.naming)
        
        await message.answer(
            f"✏️ Название сборника\n\n"
            f"Текущее: {current_title}\n\n"
            f"Введите новое название:\n"
            f"(или напишите 'авто' для авто-формирования)\n\n"
            f"ℹ️ Название будет использоваться для итогового файла",
            reply_markup=get_cancel_reply_keyboard()
        )

@router.message(F.text == "ℹ️ Справка")
async def handle_help_reply(message: Message):
    help_text = """📖 Помощь

1. Отправьте архив с FB2 файлами
2. Статусное сообщение появится под файлами
3. Используйте кнопки под сообщением для управления

Доступные действия:
📚 Слить книги - объединить все книги в один FB2
📝 Сортировать книги - изменить порядок книг
✏️ Назвать сборник - задать название для сборника
📋 Список книг - показать все загруженные книги
🗑️ Очистить сессию - удалить все загруженные книги

Команды:
/start - Начало работы
/help - Эта справка
/clear - Очистить сессию
/list - Показать список книг"""
    
    await message.answer(
        help_text,
        reply_markup=get_main_reply_keyboard()
    )

@router.message(F.text == "🗑️ Очистить сессию")
async def handle_clear_reply(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)

        if session.status_message_id:
            try:
                await bot_data.bot_instance.delete_message(
                    chat_id=chat_id,
                    message_id=session.status_message_id
                )
            except Exception:
                pass

        cleanup_user_session(user_id)

        session = get_or_create_session(user_id)
        
        await message.answer(
            "✅ Сессия очищена. Вы можете загрузить новые файлы.",
            reply_markup=get_main_reply_keyboard()
        )

@router.message(F.text == "📋 Список книг")
async def handle_list_reply(message: Message):
    user_id = message.from_user.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if not session.book_contents:
            await message.answer(
                "📭 Нет загруженных книг.",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        books_list = "\n".join([f"{i+1}. {book.title}" for i, book in enumerate(session.book_contents)])
        memory_usage = session.get_memory_usage() // (1024*1024)
        
        response = f"""📚 Статистика:
• Книг: {len(session.book_contents)}
• Память: ~{memory_usage} MB
• Название: {session.get_series_title()}

Список книг по порядку:
{books_list}"""
        
        await message.answer(
            response,
            reply_markup=get_main_reply_keyboard()
        )

@router.message(F.text == "❌ Отмена")
async def handle_cancel_reply(message: Message, state: FSMContext):
    user_id = message.from_user.id
    
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(
            "❌ Действие отменено.",
            reply_markup=get_main_reply_keyboard()
        )
    else:
        await message.answer(
            "ℹ️ Нет активных действий для отмена.",
            reply_markup=get_main_reply_keyboard()
        )

@router.callback_query(F.data == "merge_books")
async def handle_merge_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if len(session.book_contents) < 2:
            await callback.answer("❌ Нужно как минимум 2 книги для слияния.", show_alert=True)
            return
        
        try:
            await callback.answer("🔄 Начинаю слияние книг...")
            
            sorted_books = session.get_sorted_books()
            series_title = session.get_series_title()

            safe_title = "".join(c for c in series_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            output_filename = f"{safe_title}.fb2"
            output_path = Path(bot_data.config.TEMP_DIR) / str(user_id) / output_filename

            output_path.parent.mkdir(parents=True, exist_ok=True)

            success = await asyncio.get_event_loop().run_in_executor(
                None,
                bot_data.merger.create_merged_fb2,
                sorted_books,
                str(output_path),
                series_title
            )
            
            if success and output_path.exists():
                document = FSInputFile(output_path, filename=output_filename)
                await callback.message.answer_document(
                    document,
                    caption=f"📚 {series_title}\nОбъединено книг: {len(sorted_books)}"
                )

                output_path.unlink()
                
            else:
                await callback.message.answer("❌ Ошибка при создании файла.")
            
        except Exception as e:
            await callback.message.answer(f"❌ Ошибка: {str(e)}")
        
        finally:
            await update_or_create_status(chat_id, session)

@router.callback_query(F.data == "sort_books")
async def handle_sort_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if not session.book_contents:
            await callback.answer("❌ Нет книг для сортировки.", show_alert=True)
            return
        
        books_list = "\n".join([f"{i+1}. {b.title}" for i, b in enumerate(session.book_contents)])
        
        await state.set_state(BookStates.sorting)

        instruction_msg = await bot_data.bot_instance.send_message(
            chat_id=chat_id,
            text=f"📚 Текущий порядок:\n\n{books_list}\n\n"
                f"Введите новый порядок цифрами через пробел:\n"
                f"Пример: 1 3 2\n\n"
                f"❌ Для отмены напишите 'отмена' или используйте кнопку",
            reply_markup=get_cancel_reply_keyboard()
        )

        await state.update_data(instruction_msg_id=instruction_msg.message_id)
    
    await callback.answer()

@router.callback_query(F.data == "name_collection")
async def handle_name_callback(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if not session.book_contents:
            await callback.answer("❌ Нет книг для сборника.", show_alert=True)
            return
        
        current_title = session.get_series_title()
        
        await state.set_state(BookStates.naming)

        instruction_msg = await bot_data.bot_instance.send_message(
            chat_id=chat_id,
            text=f"✏️ Название сборника\n\n"
                f"Текущее: {current_title}\n\n"
                f"Введите новое название:\n"
                f"(или напишите 'авто' для авто-формирования)\n\n"
                f"❌ Для отмены напишите 'отмена' или используйте кнопку",
            reply_markup=get_cancel_reply_keyboard()
        )
        
        await state.update_data(instruction_msg_id=instruction_msg.message_id)
    
    await callback.answer()

@router.callback_query(F.data == "show_help")
async def handle_help_callback(callback: CallbackQuery):
    help_text = """📖 Помощь

1. Отправьте архив с FB2 файлами
2. Статусное сообщение появится под файлами
3. Используйте кнопки под сообщением для управления

Доступные действия:
📚 Слить книги - объединить все книги в один FB2
📝 Сортировать книги - изменить порядок книг
✏️ Назвать сборник - задать название для сборника
🗑️ Очистить сессию - удалить все загруженные книги"""
    
    await callback.message.answer(help_text)
    await callback.answer()

@router.callback_query(F.data == "clear_session")
async def handle_clear_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        
        if session.status_message_id:
            try:
                await bot_data.bot_instance.delete_message(
                    chat_id=chat_id,
                    message_id=session.status_message_id
                )
            except Exception:
                pass
        
        cleanup_user_session(user_id)

        session = get_or_create_session(user_id)
        
        await callback.answer("✅ Сессия очищена.", show_alert=True)
        
        await callback.message.answer("✅ Сессия очищена. Вы можете загрузить новые файлы.")

@router.message(F.text)
async def handle_text_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    chat_id = message.chat.id
    text = message.text.strip().lower()
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        current_state = await state.get_state()
        session = get_or_create_session(user_id)
        
        if current_state == BookStates.sorting:
            if text == "отмена":
                await state.clear()
                await message.answer(
                    "❌ Сортировка отменена.",
                    reply_markup=get_main_reply_keyboard()
                )
                return
            
            try:
                numbers = [int(n) for n in text.split()]
                count = len(session.book_contents)
                
                if len(numbers) != count or min(numbers) < 1 or max(numbers) > count:
                    await message.answer(
                        f"❌ Нужно {count} чисел от 1 до {count}.",
                        reply_markup=get_cancel_reply_keyboard()
                    )
                    return
                
                new_order = [session.book_contents[i - 1] for i in numbers]
                session.book_contents = new_order
                
                for i, book in enumerate(session.book_contents):
                    book.sort_order = i
                
                await state.clear()

                await update_or_create_status(chat_id, session)
                await message.answer(
                    "✅ Порядок книг изменен!",
                    reply_markup=get_main_reply_keyboard()
                )
                
            except ValueError:
                await message.answer(
                    "❌ Некорректный формат. Используйте числа через пробел.",
                    reply_markup=get_cancel_reply_keyboard()
                )
            except Exception:
                await message.answer(
                    "❌ Ошибка при сортировке.",
                    reply_markup=get_main_reply_keyboard()
                )
        
        elif current_state == BookStates.naming:
            if text == "отмена":
                await state.clear()
                await message.answer(
                    "❌ Переименование отменено.",
                    reply_markup=get_main_reply_keyboard()
                )
                return
            
            if text == "авто":
                session.custom_series_title = ""
                await message.answer(
                    "✅ Название сборника сброшено на авто-формирование.",
                    reply_markup=get_main_reply_keyboard()
                )
            else:
                session.custom_series_title = message.text.strip() 
                await message.answer(
                    f"✅ Название сборника изменено на: {session.custom_series_title}",
                    reply_markup=get_main_reply_keyboard()
                )
            
            await state.clear()
            await update_or_create_status(chat_id, session)

        elif text.startswith('/'):
            pass
        else:
            await message.answer(
                "ℹ️ Используйте кнопки ниже или отправьте файл с FB2 книгами.",
                reply_markup=get_main_reply_keyboard()
            )

@router.message(F.document)
async def handle_document(message: Message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    user_lock = get_or_create_lock(user_id)
    
    async with user_lock:
        session = get_or_create_session(user_id)
        document = message.document
        
        if not document.file_name or not bot_data.archive_handler.is_supported_file(document.file_name):
            supported = ", ".join(bot_data.archive_handler.supported_formats)
            await message.answer(
                f"❌ Неподдерживаемый формат. Поддерживаются: {supported}",
                reply_markup=get_main_reply_keyboard()
            )
            return
        
        try:
            processing_msg = await message.answer("⏳ Обрабатываю файл...")
            
            user_temp_dir = Path(bot_data.config.TEMP_DIR) / str(user_id)
            user_temp_dir.mkdir(exist_ok=True)
            
            file_path = user_temp_dir / document.file_name
            
            await bot_data.config.bot.download(document, destination=file_path)
            
            book_contents, temp_dir = bot_data.archive_handler.extract_and_parse_file(
                str(file_path), user_id
            )
            
            if temp_dir:
                session.temp_dirs.append(temp_dir)
            
            if file_path.exists():
                file_path.unlink()
            
            await processing_msg.delete()
            
            if not book_contents:
                await message.answer(
                    "❌ FB2-книги не найдены",
                    reply_markup=get_main_reply_keyboard()
                )
                return
            
            books_before = len(session.book_contents)
            
            current_time = datetime.now()
            is_new_batch = False
            
            if books_before == 0:
                is_new_batch = True
            elif session.last_file_time:
                time_since_last = current_time - session.last_file_time
                if time_since_last > timedelta(seconds=2):
                    is_new_batch = True
                else:
                    is_new_batch = False
            else:
                is_new_batch = True
            
            session.last_file_time = current_time
            
            start_order = len(session.book_contents)
            for i, book in enumerate(book_contents):
                book.sort_order = start_order + i
                session.book_contents.append(book)
            
            if is_new_batch:
                await create_status_message_at_bottom(chat_id, session)
            else:
                await update_or_create_status(chat_id, session, force_new=False)
            
        except Exception as e:
            await message.answer(
                f"❌ Ошибка обработки файла: {str(e)}",
                reply_markup=get_main_reply_keyboard()
            )
