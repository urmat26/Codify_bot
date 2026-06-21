import os
import sys
import logging
import asyncio
import platform
import signal
import html
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, FSInputFile
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

from config import BOT_NAME, WELCOME_MESSAGE, HELP_MESSAGE
from prompts import SYSTEM_PROMPT
from ai import ask_ai
from session import add_message, get_session, clear_session
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


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Расписание"), KeyboardButton(text="💰 Цены")],
            [KeyboardButton(text="📍 Адрес"),      KeyboardButton(text="✏️ Записаться")],
            [KeyboardButton(text="📚 Курсы"),      KeyboardButton(text="👦 Возраст")],
            [KeyboardButton(text="🪙 CodeCoin"),   KeyboardButton(text="📞 Контакты")],
            [KeyboardButton(text="🔄 Новый чат")],
        ],
        resize_keyboard=True,
        persistent=True
    )


def extra_inline(data: str) -> InlineKeyboardMarkup | None:
    rows = {
        "courses": [[InlineKeyboardButton(text="✏️ Записаться на пробный", url="https://wa.me/996500431430")]],
        "address": [[InlineKeyboardButton(text="📍 7-й мкр на карте", url="https://go.2gis.com/Aw4me"),
                     InlineKeyboardButton(text="📍 Ибраимова на карте", url="https://go.2gis.com/yhL33")]],
        "contacts": [[InlineKeyboardButton(text="💬 WhatsApp", url="https://wa.me/996500431430"),
                      InlineKeyboardButton(text="📸 Instagram", url="https://www.instagram.com/codify.kids/")]],
        "prices": [[InlineKeyboardButton(text="💬 Узнать цену в WhatsApp", url="https://wa.me/996500431430")]],
        "schedule": [[InlineKeyboardButton(text="✏️ Выбрать время", url="https://wa.me/996500431430")]],
        "enroll": [[InlineKeyboardButton(text="💬 WhatsApp", url="https://wa.me/996500431430"),
                    InlineKeyboardButton(text="✈️ Telegram", url="https://t.me/codify_community")]],
        "online": [[InlineKeyboardButton(text="💬 Записаться онлайн", url="https://wa.me/996500431430")]],
        "age": [[InlineKeyboardButton(text="📞 Записать на диагностику", url="https://wa.me/996500431430")]],
        "mentors": [[InlineKeyboardButton(text="📞 Записаться к ментору", url="https://wa.me/996500431430")]],
        "codecoin": [[InlineKeyboardButton(text="🎁 Посмотреть мерч", url="https://www.instagram.com/codify.kids/")]],
        "about": [[InlineKeyboardButton(text="🌐 Сайт Codify", url="https://codifylab.com")]],
    }
    btns = rows.get(data)
    return InlineKeyboardMarkup(inline_keyboard=btns) if btns else None


ANSWERS_MAP = {
    "codecoin": answers.CODECOIN, "age": answers.AGE,
    "courses": answers.COURSES, "schedule": answers.SCHEDULE,
    "address": answers.ADDRESS, "online": answers.ONLINE,
    "prices": answers.PRICES, "enroll": answers.ENROLL,
    "contacts": answers.CONTACTS, "mentors": answers.MENTORS,
    "about": answers.ABOUT, "faq": answers.FAQ,
}

BUTTON_MAP = {
    "📚 Курсы": "courses", "📅 Расписание": "schedule",
    "📍 Адрес": "address", "📞 Контакты": "contacts",
    "💰 Цены": "prices", "✏️ Записаться": "enroll",
    "🪙 CodeCoin": "codecoin", "👦 Возраст": "age",
    "🔄 Новый чат": "reset",
}

bot = Bot(token=os.getenv("BOT_TOKEN"), default=DefaultBotProperties(parse_mode="HTML"))
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


async def send_answer(target: Message, key: str) -> None:
    text = ANSWERS_MAP.get(key)
    if not text:
        return
    inline_kb = extra_inline(key)
    reply = inline_kb or main_keyboard()
    if key == "about":
        photo = FSInputFile(os.path.join(ASSETS_DIR, "school-photo.jpg"))
        await target.answer_photo(photo=photo, caption=text, reply_markup=reply)
    else:
        await target.answer(text, reply_markup=reply)


async def handle_message(target: Message, user_id: int, text: str) -> None:
    cached = cache_get(text)
    if cached:
        add_message(user_id, "user", text)
        add_message(user_id, "assistant", cached)
        await target.answer(cached, reply_markup=main_keyboard())
        return

    add_message(user_id, "user", text)

    try:
        history = get_session(user_id)
        api_messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        answer = await ask_ai(api_messages)
        cache_set(text, answer)
        add_message(user_id, "assistant", answer)
        safe = html.escape(answer)
        await target.answer(safe, reply_markup=main_keyboard())

    except Exception as e:
        logger.error("AI Error: %s", e)
        err = str(e).lower()
        phone = "+996 500 431 430"
        if "429" in err or "quota" in err or "rate limit" in err:
            msg = (
                "😅 Слишком много запросов. Подождите минуту или напишите менеджеру:\n"
                "💬 WhatsApp: https://wa.me/996500431430\n"
                f"📞 {phone}, +996 700 431 430"
            )
        else:
            msg = (
                "❌ Произошла ошибка. Попробуйте позже:\n"
                f"📞 {phone} / info@codifylab.com"
            )
        await target.answer(msg, reply_markup=main_keyboard())


# --- Start / Help ---

@dp.message(CommandStart())
async def start_handler(message: Message) -> None:
    clear_session(message.from_user.id)
    logo = FSInputFile(os.path.join(ASSETS_DIR, "favicon.webp"))
    await message.answer_photo(photo=logo, caption=WELCOME_MESSAGE, reply_markup=main_keyboard())


@dp.message(Command("help"))
async def help_handler(message: Message) -> None:
    await message.answer(HELP_MESSAGE, reply_markup=main_keyboard())


@dp.message(Command("cancel"))
async def cancel_handler(message: Message, state: FSMContext) -> None:
    current = await state.get_state()
    if current is None:
        return
    await state.clear()
    await message.answer("❌ Запись отменена.", reply_markup=main_keyboard())


# --- Enrollment FSM ---

async def start_enrollment(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Enrollment.name)
    cancel_kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="Отмена")]],
        resize_keyboard=True
    )
    await message.answer(
        "✏️ <b>Запись на пробный урок</b>\n\n"
        "Пожалуйста, напишите ваше <b>Имя и Фамилию</b>:",
        parse_mode="HTML",
        reply_markup=cancel_kb
    )


@dp.message(Enrollment.name)
async def process_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if name.lower() == "отмена":
        await state.clear()
        return await message.answer("❌ Запись отменена.", reply_markup=main_keyboard())
    if len(name) < 2:
        return await message.answer("Пожалуйста, напишите корректные имя и фамилию.")
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
        f"Приятно познакомиться, <b>{name}</b>!\n\n"
        "Теперь укажите ваш <b>номер телефона</b>:",
        parse_mode="HTML",
        reply_markup=phone_kb
    )


@dp.message(Enrollment.phone)
async def process_phone(message: Message, state: FSMContext) -> None:
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
    else:
        text = message.text.strip()
        if text.lower() == "отмена":
            await state.clear()
            return await message.answer("❌ Запись отменена.", reply_markup=main_keyboard())
        clean = "".join(filter(str.isdigit, text))
        if len(clean) < 6:
            return await message.answer("Пожалуйста, введите корректный номер телефона:")
        phone = text

    user_data = await state.get_data()
    name = user_data.get("name", "")
    await state.clear()

    logger.info("Запись: Имя=%s, Телефон=%s, ChatID=%d", name, phone, message.chat.id)

    manager_id = os.getenv("MANAGER_CHAT_ID")
    if manager_id:
        try:
            await bot.send_message(
                int(manager_id),
                f"📩 <b>Новая заявка на пробный!</b>\n\n"
                f"👤 <b>Имя:</b> {name}\n"
                f"📞 <b>Телефон:</b> {phone}\n"
                f"🆔 ChatID: {message.chat.id}",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error("Failed to notify manager: %s", e)

    await message.answer(
        f"🎉 <b>Заявка на пробный урок принята!</b>\n\n"
        f"👤 <b>Имя:</b> {name}\n"
        f"📞 <b>Телефон:</b> {phone}\n\n"
        f"Менеджер свяжется с вами в ближайшее время! 😊\n\n"
        f"💬 WhatsApp: https://wa.me/996500431430\n"
        f"📞 +996 500 431 430, +996 700 431 430",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# --- Command handlers ---

@dp.message(Command("courses"))
async def courses_handler(message: Message) -> None:
    await send_answer(message, "courses")

@dp.message(Command("mentors"))
async def mentors_handler(message: Message) -> None:
    await send_answer(message, "mentors")

@dp.message(Command("prices"))
async def prices_handler(message: Message) -> None:
    await send_answer(message, "prices")

@dp.message(Command("address"))
async def address_handler(message: Message) -> None:
    await send_answer(message, "address")


# --- Text handler ---

@dp.message(F.text)
async def text_handler(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    clean = text.lower()

    if "записаться" in clean or "запись" in clean or "пробный" in clean:
        return await start_enrollment(message, state)
    if "онлайн" in clean:
        return await send_answer(message, "online")

    btn_key = BUTTON_MAP.get(text)
    if btn_key == "reset":
        clear_session(message.from_user.id)
        return await message.answer("🔄 История очищена! Задайте новый вопрос 👇", reply_markup=main_keyboard())
    if btn_key:
        return await send_answer(message, btn_key)

    chat_id = message.chat.id
    if chat_id in pending:
        return await message.answer("⏳ Уже думаю... Подождите немного!", reply_markup=main_keyboard())

    pending.add(chat_id)
    try:
        await handle_message(message, message.from_user.id, text)
    finally:
        pending.discard(chat_id)


# --- Callback handler (legacy, for old inline messages) ---

@dp.callback_query()
async def callback_handler(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = callback.data
    if data == "enroll":
        await start_enrollment(callback.message, state)
    elif data in ANSWERS_MAP:
        await send_answer(callback.message, data)
    else:
        await callback.message.answer("Неизвестная команда", reply_markup=main_keyboard())


async def health_check(request):
    return web.Response(text="OK")


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 7860))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health check server started on port %d", port)


# --- Main ---

async def main() -> None:
    token = os.getenv("BOT_TOKEN")
    if not token:
        logger.error("BOT_TOKEN не указан. Создайте файл .env на основе .env.example")
        return
    if not os.getenv("GROQ_API_KEY"):
        logger.error("GROQ_API_KEY не указан. Создайте файл .env на основе .env.example")
        return

    _kill_previous()
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    # Start health check server for Hugging Face Spaces
    asyncio.create_task(start_health_server())

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
