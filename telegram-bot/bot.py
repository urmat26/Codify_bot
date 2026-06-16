import os
import sys
import logging
import asyncio
import platform
import signal
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
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

pending: set[int] = set()

class Enrollment(StatesGroup):
    name = State()
    phone = State()

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

LINK_BUTTONS = {
    "courses": [[InlineKeyboardButton(text="✏️ Записаться на пробный", url="https://wa.me/996500431430")]],
    "enroll": [[InlineKeyboardButton(text="💬 WhatsApp", url="https://wa.me/996500431430"), InlineKeyboardButton(text="✈️ Telegram", url="https://t.me/codify_community")]],
    "prices": [[InlineKeyboardButton(text="💬 Узнать цену в WhatsApp", url="https://wa.me/996500431430")]],
    "address": [[InlineKeyboardButton(text="📍 7-й мкр на карте", url="https://go.2gis.com/Aw4me"), InlineKeyboardButton(text="📍 Ибраимова на карте", url="https://go.2gis.com/yhL33")]],
    "contacts": [[InlineKeyboardButton(text="💬 WhatsApp", url="https://wa.me/996500431430"), InlineKeyboardButton(text="📸 Instagram", url="https://www.instagram.com/codify.kids/")]],
    "schedule": [[InlineKeyboardButton(text="✏️ Выбрать время", url="https://wa.me/996500431430")]],
    "online": [[InlineKeyboardButton(text="💬 Записаться онлайн", url="https://wa.me/996500431430")]],
    "age": [[InlineKeyboardButton(text="📞 Записать на диагностику", url="https://wa.me/996500431430")]],
    "about": [[InlineKeyboardButton(text="🌐 Сайт Codify", url="https://codifylab.com")]],
    "faq": [[InlineKeyboardButton(text="💬 Остались вопросы?", url="https://wa.me/996500431430")]],
    "mentors": [[InlineKeyboardButton(text="📞 Записаться к ментору", url="https://wa.me/996500431430")]],
    "codecoin": [[InlineKeyboardButton(text="🎁 Посмотреть мерч", url="https://www.instagram.com/codify.kids/")]],
}

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
dp = Dispatcher(storage=MemoryStorage())


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


def merge_keyboard(data: str | None) -> InlineKeyboardMarkup:
    if not data:
        return MAIN_KEYBOARD
    extra = LINK_BUTTONS.get(data)
    if not extra:
        return MAIN_KEYBOARD
    merged = MAIN_KEYBOARD.inline_keyboard.copy()
    merged.extend(extra)
    return InlineKeyboardMarkup(inline_keyboard=merged)


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
        phone = "+996 500 431 430"
        phone2 = "+996 700 431 430"
        if "429" in error_text or "quota" in error_text or "rate limit" in error_text:
            msg = (
                "😅 Слишком много запросов. Подождите минуту или напишите менеджеру:\n"
                f"💬 WhatsApp: https://wa.me/996500431430\n"
                f"✈️ Telegram: @codify_community\n"
                f"📞 {phone}, {phone2}"
            )
        elif "api" in error_text or "key" in error_text:
            msg = (
                "⚙️ Проблема с подключением к AI. Обратитесь к менеджеру напрямую:\n"
                f"💬 WhatsApp: https://wa.me/996500431430\n"
                f"📞 {phone}, {phone2}"
            )
        else:
            msg = (
                f"❌ Произошла ошибка. Попробуйте позже или напишите менеджеру:\n"
                f"💬 WhatsApp: https://wa.me/996500431430\n"
                f"📞 {phone}, {phone2}"
            )
        await target.answer(msg)


@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    clear_session(message.from_user.id)
    await message.answer(WELCOME_MESSAGE, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_MESSAGE, reply_markup=MAIN_KEYBOARD)


@dp.message(Command("cancel"))
@dp.message(F.text.lower() == "отмена")
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("❌ Запись на пробный урок отменена.", reply_markup=MAIN_KEYBOARD)


# --- Enrollment FSM ---

async def start_enrollment(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Enrollment.name)
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True
    )
    await message.answer(
        "✏️ *Запись на пробный урок*\n\n"
        "Пожалуйста, напишите ваше *Имя и Фамилию*:\n"
        "_(Для отмены напишите «отмена»)_",
        parse_mode="Markdown",
        reply_markup=cancel_kb
    )


@dp.message(Enrollment.name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        return await message.answer("Пожалуйста, напишите корректные имя и фамилию (минимум 2 символа).")
    await state.update_data(name=name)
    await state.set_state(Enrollment.phone)

    phone_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером телефона", request_contact=True)],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await message.answer(
        f"Приятно познакомиться, *{name}*!\n\n"
        "Теперь укажите ваш *номер телефона* (или нажмите кнопку ниже):",
        parse_mode="Markdown",
        reply_markup=phone_kb
    )


@dp.message(Enrollment.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
    else:
        text = message.text.strip()
        clean = "".join(filter(str.isdigit, text))
        if len(clean) < 6:
            return await message.answer("Пожалуйста, введите корректный номер телефона:")
        phone = text

    user_data = await state.get_data()
    name = user_data.get("name", "")
    await state.clear()

    logger.info("Запись: Имя=%s, Телефон=%s, ChatID=%d", name, phone, message.chat.id)

    text = (
        f"🎉 *Заявка на пробный урок принята!*\n\n"
        f"👤 *Имя:* {name}\n"
        f"📞 *Телефон:* {phone}\n\n"
        f"Менеджер свяжется с вами в ближайшее время! 😊\n\n"
        f"Контакты:\n"
        f"💬 WhatsApp: https://wa.me/996500431430\n"
        f"✈️ Telegram: @codify_community\n"
        f"📞 +996 500 431 430, +996 700 431 430"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD)


# --- Command handlers ---

@dp.message(Command("courses"))
async def courses_handler(message: Message) -> None:
    await message.answer(answers.COURSES, reply_markup=merge_keyboard("courses"))


@dp.message(Command("mentors"))
async def mentors_handler(message: Message) -> None:
    await message.answer(answers.MENTORS, reply_markup=merge_keyboard("mentors"))


@dp.message(Command("prices"))
async def prices_handler(message: Message) -> None:
    await message.answer(answers.PRICES, reply_markup=merge_keyboard("prices"))


@dp.message(Command("address"))
async def address_handler(message: Message) -> None:
    await message.answer(answers.ADDRESS, reply_markup=merge_keyboard("address"))


# --- Text handler (free text & keyboard words) ---

@dp.message(F.text)
async def text_handler(message: Message, state: FSMContext) -> None:
    chat_id = message.chat.id
    text = message.text.strip()

    clean = text.lower()
    if "записаться" in clean or "запись" in clean or "пробный" in clean:
        return await start_enrollment(message, state)
    if "онлайн" in clean or "online" in clean:
        return await message.answer(answers.ONLINE, reply_markup=merge_keyboard("online"))

    if chat_id in pending:
        return await message.answer("⏳ Уже думаю над вашим вопросом... Подождите немного!", reply_markup=MAIN_KEYBOARD)

    pending.add(chat_id)
    try:
        await handle_message(message, message.from_user.id, text)
    finally:
        pending.discard(chat_id)


# --- Callback handler ---

@dp.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    data = callback.data
    if data == "enroll":
        await start_enrollment(callback.message, state)
        return

    answer = ANSWERS_MAP.get(data)
    if answer:
        await callback.message.answer(answer, reply_markup=merge_keyboard(data))
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
