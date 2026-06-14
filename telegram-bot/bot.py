import os
import sys
import logging
import asyncio
import platform
import signal
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command, CommandStart
from aiogram.client.default import DefaultBotProperties

from config import BOT_NAME, WELCOME_MESSAGE, HELP_MESSAGE, ERROR_MESSAGE, QUOTA_MESSAGE
from prompts import SYSTEM_PROMPT
from ai import ask_ai
from session import add_message, get_session, clear_session, cleanup
from cache import cache_get, cache_set
import answers

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

LOCK_FILE = "bot.lock"

MAIN_KEYBOARD = InlineKeyboardMarkup(inline_keyboard=[
    [
        InlineKeyboardButton(text="🪙 CodeCoin", callback_data="codecoin"),
        InlineKeyboardButton(text="👦 Возраст", callback_data="age"),
    ],
    [
        InlineKeyboardButton(text="📚 Курсы", callback_data="courses"),
        InlineKeyboardButton(text="📅 Расписание", callback_data="schedule"),
    ],
    [
        InlineKeyboardButton(text="📍 Адрес", callback_data="address"),
        InlineKeyboardButton(text="💻 Онлайн", callback_data="online"),
    ],
    [
        InlineKeyboardButton(text="💰 Цены", callback_data="prices"),
        InlineKeyboardButton(text="✏️ Записаться", callback_data="enroll"),
    ],
    [
        InlineKeyboardButton(text="📞 Контакты", callback_data="contacts"),
        InlineKeyboardButton(text="👨‍🏫 Менторы", callback_data="mentors"),
    ],
    [
        InlineKeyboardButton(text="ℹ️ О школе", callback_data="about"),
        InlineKeyboardButton(text="❓ FAQ", callback_data="faq"),
    ],
])

ANSWERS_MAP = {
    "codecoin": answers.CODECOIN,
    "age": answers.AGE,
    "courses": answers.COURSES,
    "schedule": answers.SCHEDULE,
    "address": answers.ADDRESS,
    "online": answers.ONLINE,
    "prices": answers.PRICES,
    "enroll": answers.ENROLL,
    "contacts": answers.CONTACTS,
    "mentors": answers.MENTORS,
    "about": answers.ABOUT,
    "faq": answers.FAQ,
}

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode=None))
dp = Dispatcher()


def _kill_previous() -> None:
    if not os.path.exists(LOCK_FILE):
        return
    try:
        with open(LOCK_FILE) as f:
            pid = int(f.read().strip())
    except (ValueError, OSError):
        return
    if pid == os.getpid():
        return
    try:
        if platform.system() == "Windows":
            import subprocess
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True, shell=True
            )
        else:
            os.kill(pid, signal.SIGKILL)
        logger.info("Killed previous bot instance (PID %d)", pid)
    except (ProcessLookupError, OSError):
        pass


async def handle_message(target: Message, user_id: int, text: str) -> None:
    cached = cache_get(text)
    if cached:
        add_message(user_id, "user", text)
        add_message(user_id, "assistant", cached)
        await target.answer(cached)
        return

    add_message(user_id, "user", text)

    try:
        history = get_session(user_id)
        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history

        answer = await ask_ai(api_messages)
        cache_set(text, answer)
        add_message(user_id, "assistant", answer)
        await target.answer(answer)

    except Exception as e:
        logger.error("AI Error: %s", e)
        error_text = str(e).lower()
        if "429" in error_text or "quota" in error_text or "rate limit" in error_text:
            msg = QUOTA_MESSAGE
        else:
            msg = ERROR_MESSAGE
        await target.answer(msg)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    clear_session(message.from_user.id)
    await message.answer(WELCOME_MESSAGE, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_MESSAGE, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("courses"))
async def courses_handler(message: Message) -> None:
    await message.answer(answers.COURSES, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("mentors"))
async def mentors_handler(message: Message) -> None:
    await message.answer(answers.MENTORS, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("prices"))
async def prices_handler(message: Message) -> None:
    await message.answer(answers.PRICES, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("address"))
async def address_handler(message: Message) -> None:
    await message.answer(answers.ADDRESS, reply_markup=MAIN_KEYBOARD)


@dp.message(F.text)
async def text_handler(message: Message) -> None:
    await handle_message(message, message.from_user.id, message.text)


@dp.callback_query()
async def callback_handler(callback: CallbackQuery) -> None:
    await callback.answer()

    answer = ANSWERS_MAP.get(callback.data)
    if answer:
        await callback.message.answer(answer, reply_markup=MAIN_KEYBOARD)
    else:
        await callback.message.answer("Неизвестная команда", reply_markup=MAIN_KEYBOARD)


async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не указан. Создайте файл .env на основе .env.example")
        return

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY не указан. Создайте файл .env на основе .env.example")
        return

    _kill_previous()
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    logger.info("Бот %s запущен!", BOT_NAME)
    print(f"Бот {BOT_NAME} запущен!")
    print("Напишите /start в Telegram, чтобы проверить.")

    try:
        await dp.start_polling(bot)
    finally:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)


if __name__ == "__main__":
    asyncio.run(main())
