import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import BOT_TOKEN
from school_data import SCHOOL_DATA
from prompts import QUICK_MESSAGES
from ai import ask_openrouter


# ===================================================
# ЛОГИРОВАНИЕ
# ===================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ===================================================
# ИНИЦИАЛИЗАЦИЯ
# ===================================================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# История диалогов: { chat_id: [{"role": ..., "parts": [...]}] }
chat_histories: dict[int, list] = {}

# Блокировка двойных запросов
pending: set[int] = set()

# ===================================================
# КЛАВИАТУРЫ
# ===================================================
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

class EnrollmentStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()

def contact_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💬 WhatsApp",  url=SCHOOL_DATA["whatsapp"]),
            InlineKeyboardButton(text="✈️ Telegram",  url=SCHOOL_DATA["telegram"]),
        ],
        [
            InlineKeyboardButton(text="📸 Instagram",  url=SCHOOL_DATA["instagram"]),
            InlineKeyboardButton(text="📘 Facebook",  url=SCHOOL_DATA["facebook"]),
        ],
        [
            InlineKeyboardButton(text="🌐 Сайт",      url=SCHOOL_DATA["website"]),
        ]
    ])

def address_inline() -> InlineKeyboardMarkup:
    branches = SCHOOL_DATA["branches"]
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🗺 {b['name']}", url=b["map"])]
        for b in branches
    ])

# ===================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===================================================
def get_history(chat_id: int) -> list:
    if chat_id not in chat_histories:
        chat_histories[chat_id] = []
    return chat_histories[chat_id]

def add_to_history(chat_id: int, role: str, text: str):
    history = get_history(chat_id)
    history.append({"role": role, "parts": [{"text": text}]})
    # Обрезаем до MAX_HISTORY_PAIRS пар
    from config import MAX_HISTORY_PAIRS
    max_entries = MAX_HISTORY_PAIRS * 2
    if len(history) > max_entries:
        chat_histories[chat_id] = history[-max_entries:]

def clear_history(chat_id: int):
    chat_histories[chat_id] = []

# ===================================================
# ГОТОВЫЕ ОТВЕТЫ (без AI)
# ===================================================
async def send_address(message: Message):
    branches = SCHOOL_DATA["branches"]
    text = "📍 *Адреса филиалов Codify в Бишкеке:*\n\n"
    for i, b in enumerate(branches, 1):
        text += f"*{i}. {b['name']}*\n"
        text += f"🏢 {b['address']}"
        if b["landmark"]:
            text += f" ({b['landmark']})"
        text += "\n\n"
    text += f"📞 Телефон: {SCHOOL_DATA['phone']}"

    await message.answer(text, parse_mode="Markdown",
                         reply_markup=address_inline())

async def send_courses(message: Message):
    courses = SCHOOL_DATA["courses"]
    text = "📚 *Путь ребёнка в IT — 8 этапов Codify:*\n\n"

    groups = {}
    for c in courses:
        age = c["age"]
        if age not in groups:
            groups[age] = []
        groups[age].append(c)

    for age, clist in groups.items():
        text += f"*👤 {age}:*\n"
        for c in clist:
            text += f"  • Этап {c['stage']}: *{c['name']}* — {c['duration']}\n"
        text += "\n"

    text += f"✅ Офлайн и онлайн форматы\n"
    text += f"📞 Запись: {SCHOOL_DATA['phone']}"

    await message.answer(text, parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="✏️ Записаться", url=SCHOOL_DATA["whatsapp"])],
                             [InlineKeyboardButton(text="🌐 Сайт Codify", url=SCHOOL_DATA["website"])],
                         ]))

async def send_contacts(message: Message):
    text = (
        "📞 <b>Контакты Codify:</b>\n\n"
        f"📱 <b>Основной телефон / WhatsApp:</b> <a href='https://wa.me/996500431430'>{SCHOOL_DATA['phone']}</a>\n"
        f"📱 <b>Второй номер / Telegram:</b> <a href='https://t.me/codify_community'>{SCHOOL_DATA['phone2']}</a> (@codify_community)\n\n"
        f"📸 <b>Instagram:</b> <a href='{SCHOOL_DATA['instagram']}'>{SCHOOL_DATA['instagram_handle']}</a>\n"
        f"📘 <b>Facebook:</b> <a href='{SCHOOL_DATA['facebook']}'>Codify Teens</a>\n"
        f"🌐 <b>Сайт:</b> <a href='{SCHOOL_DATA['website']}'>codifylab.com</a>\n"
        f"📧 <b>Email:</b> {SCHOOL_DATA['email']}"
    )
    await message.answer(text, parse_mode="HTML",
                         reply_markup=contact_inline(),
                         disable_web_page_preview=True)

async def send_codecoin(message: Message):
    cc = SCHOOL_DATA["codecoin"]
    merch = cc["merch"]
    text = (
        f"🪙 *CodeCoin — внутренняя валюта Codify*\n\n"
        f"📝 *Как заработать:*\n"
        f"{cc['earn']}\n\n"
        f"🎁 *На что обменять:*\n"
    )
    for m in merch:
        text += f"  • {m['item']} — {m['price']}\n"
    text += f"\n💡 {cc['redeem']}"
    await message.answer(text, parse_mode="Markdown")

async def send_schedule(message: Message):
    slots = SCHOOL_DATA["schedule"]["time_slots"]
    slots_text = "\n".join(f"  • {s}" for s in slots)
    text = (
        f"📅 *Расписание занятий Codify:*\n\n"
        f"📆 *Дней в неделю:* {SCHOOL_DATA['schedule']['days_per_week']}\n"
        f"⏱ *Длительность урока:* {SCHOOL_DATA['schedule']['lesson_duration']}\n\n"
        f"🕐 *Доступные временные слоты:*\n{slots_text}\n\n"
        f"📝 Время выбираете при записи.\n"
        f"📞 Записаться: {SCHOOL_DATA['phone']}"
    )
    await message.answer(text, parse_mode="Markdown",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                             [InlineKeyboardButton(text="✏️ Записаться в WhatsApp", url=SCHOOL_DATA["whatsapp"])]
                         ]))

# ===================================================
# ОБРАБОТЧИКИ КОМАНД
# ===================================================
@dp.message(CommandStart())
async def cmd_start(message: Message):
    clear_history(message.chat.id)
    name = message.from_user.first_name or "друг"
    text = (
        f"👋 Привет, *{name}*!\n\n"
        f"Я *Кодик* — ассистент IT-школы программирования *Codify* 🎓\n\n"
        f"Помогу узнать:\n"
        f"• 📚 Курсы и программы обучения\n"
        f"• 📅 Расписание и временные слоты\n"
        f"• 📍 Адреса 3 филиалов в Бишкеке\n"
        f"• 💰 Стоимость и рассрочка\n"
        f"• 🪙 Система CodeCoin\n"
        f"• ✏️ Как записаться\n\n"
        f"Просто напиши вопрос или нажми кнопку 👇"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        f"🎓 *Как пользоваться ботом Codify:*\n\n"
        f"Просто задай вопрос! Например:\n"
        f"• _«Какие курсы для детей 10 лет?»_\n"
        f"• _«Сколько стоит обучение?»_\n"
        f"• _«Где находится школа?»_\n"
        f"• _«Что такое CodeCoin?»_\n\n"
        f"*Кнопки меню:*\n"
        f"📅 Расписание • 💰 Цены • 📍 Адрес • ✏️ Записаться\n"
        f"📚 Курсы • 👦 Возраст • 💻 Онлайн • 🪙 CodeCoin\n"
        f"🔄 Новый чат • 📞 Контакты\n\n"
        f"📞 *Менеджер:* {SCHOOL_DATA['phone']}"
    )
    await message.answer(text, parse_mode="Markdown", reply_markup=main_keyboard())

@dp.message(Command("reset"))
async def cmd_reset(message: Message):
    clear_history(message.chat.id)
    await message.answer("🔄 История очищена! Задай новый вопрос 👇",
                         reply_markup=main_keyboard())

@dp.message(Command("contacts"))
async def cmd_contacts(message: Message):
    await send_contacts(message)

# ===================================================
# ОБРАБОТЧИК КНОПОК И СООБЩЕНИЙ
# ===================================================

# Словарь кнопок: текст кнопки → специальный обработчик или ключ для AI
BUTTON_HANDLERS = {
    "📍 Адрес":    "special_address",
    "📚 Курсы":    "special_courses",
    "📞 Контакты": "special_contacts",
    "🪙 CodeCoin": "special_codecoin",
    "📅 Расписание": "special_schedule",
    "🔄 Новый чат": "special_reset",
    "💰 Цены":     "special_prices",
    "✏️ Записаться": "special_enroll",
    "👦 Возраст":  QUICK_MESSAGES["age"],
    "💻 Онлайн":   "special_online",
}

async def send_prices(message: Message):
    pricing = SCHOOL_DATA["pricing"]
    text = (
        "💰 <b>Цены Codify:</b>\n\n"
        "🟢 <b>10 000 сом</b> — цена за 1 месяц обучения\n\n"
        "📅 <b>Стоимость курсов по длительности:</b>\n"
        "  • 4 месяца — <b>40 000 сом</b>\n"
        "  • 5 месяцев — <b>50 000 сом</b>\n\n"
        "💳 Доступна рассрочка без переплат — платите ежемесячно равными частями.\n\n"
        f"📞 Записаться: {pricing['contact']} / {pricing['contact2']}"
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 WhatsApp", url=pricing["whatsapp"]),
                InlineKeyboardButton(text="✈️ Telegram", url=pricing["telegram"]),
            ]
        ])
    )

async def send_online_info(message: Message):
    text = (
        "💻 *Онлайн-обучение в IT-школе Codify*\n\n"
        "Вы можете учиться из любой точки мира! Все наши курсы доступны в онлайн-формате.\n\n"
        "Для перевода чата на менеджера или записи на пробный урок, свяжитесь напрямую:\n\n"
        "💬 *WhatsApp:* [Связаться по WhatsApp](https://wa.me/996500431430)\n"
        "✈️ *Telegram:* [Написать в Telegram](https://t.me/codify_community) (@codify_community)\n"
        "📞 *Основной номер:* +996 500 431 430\n"
        "📞 *Второй номер:* +996 700 431 430"
    )
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 WhatsApp", url="https://wa.me/996500431430"),
                InlineKeyboardButton(text="✈️ Telegram", url="https://t.me/codify_community")
            ]
        ]),
        disable_web_page_preview=True
    )

async def start_enrollment(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(EnrollmentStates.waiting_for_name)
    await message.answer(
        "✏️ *Запись на пробный урок*\n\n"
        "Пожалуйста, напишите ваше **Имя и Фамилию**:\n"
        "_(Для отмены напишите «отмена»)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="Отмена")]],
            resize_keyboard=True
        )
    )

# --- Enrollment FSM Handlers ---

@dp.message(Command("cancel"))
@dp.message(F.text.lower() == "отмена")
async def cancel_enrollment(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.clear()
    await message.answer("❌ Запись на пробный урок отменена.", reply_markup=main_keyboard())

@dp.message(EnrollmentStates.waiting_for_name)
async def process_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if name.lower() == "отмена":
        await state.clear()
        return await message.answer("❌ Запись отменена.", reply_markup=main_keyboard())
    if len(name) < 2:
        return await message.answer("Пожалуйста, напишите корректные имя и фамилию (минимум 2 символа).")
    
    await state.update_data(name=name)
    await state.set_state(EnrollmentStates.waiting_for_phone)
    
    phone_keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером телефона", request_contact=True)],
            [KeyboardButton(text="Отмена")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        f"Приятно познакомиться, *{name}*!\n\n"
        "Теперь укажите ваш **номер телефона** (или нажмите кнопку ниже, чтобы поделиться им):",
        parse_mode="Markdown",
        reply_markup=phone_keyboard
    )

@dp.message(EnrollmentStates.waiting_for_phone)
async def process_phone(message: Message, state: FSMContext):
    phone = ""
    if message.contact:
        phone = message.contact.phone_number
    else:
        text_val = message.text.strip() if message.text else ""
        if text_val.lower() == "отмена":
            await state.clear()
            return await message.answer("❌ Запись отменена.", reply_markup=main_keyboard())
        # Простая проверка номера телефона
        clean_phone = "".join(filter(str.isdigit, text_val))
        if len(clean_phone) < 6:
            return await message.answer("Пожалуйста, введите корректный номер телефона или нажмите кнопку «Поделиться номером телефона»:")
        phone = text_val
    
    user_data = await state.get_data()
    name = user_data.get("name")
    
    await state.clear()
    
    logger.info(f"🆕 ЗАПИСЬ НА ПРОБНЫЙ УРОК: Имя: {name}, Телефон: {phone}, Chat ID: {message.chat.id}")
    
    success_text = (
        f"🎉 *Заявка на пробный урок принята!*\n\n"
        f"👤 *Имя:* {name}\n"
        f"📞 *Телефон:* {phone}\n\n"
        f"Менеджер свяжется с вами в ближайшее время, чтобы подобрать удобные дату и время! 😊\n\n"
        f"Если у вас возникнут вопросы, наши контакты:\n"
        f"💬 WhatsApp: [Написать менеджеру](https://wa.me/996500431430)\n"
        f"✈️ Telegram: @codify_community (https://t.me/codify_community)\n"
        f"📞 Телефон: +996 500 431 430, +996 700 431 430"
    )
    
    await message.answer(
        success_text,
        parse_mode="Markdown",
        reply_markup=main_keyboard(),
        disable_web_page_preview=True
    )

@dp.message(F.text)
async def handle_message(message: Message, state: FSMContext):
    chat_id = message.chat.id
    text = message.text

    # Специальные кнопки без AI
    handler = BUTTON_HANDLERS.get(text)

    if handler == "special_address":
        return await send_address(message)
    if handler == "special_courses":
        return await send_courses(message)
    if handler == "special_contacts":
        return await send_contacts(message)
    if handler == "special_codecoin":
        return await send_codecoin(message)
    if handler == "special_schedule":
        return await send_schedule(message)
    if handler == "special_reset":
        clear_history(chat_id)
        return await message.answer("🔄 История очищена! Задай новый вопрос 👇",
                                    reply_markup=main_keyboard())
    if handler == "special_enroll":
        return await start_enrollment(message, state)
    if handler == "special_prices":
        return await send_prices(message)
    if handler == "special_online":
        return await send_online_info(message)

    # Проверка ключевых слов
    clean_text = text.lower().strip()
    if "записаться" in clean_text or "запись" in clean_text or "пробный" in clean_text:
        return await start_enrollment(message, state)
    if "онлайн" in clean_text or "online" in clean_text:
        return await send_online_info(message)

    # Блокировка двойных запросов
    if chat_id in pending:
        return await message.answer(
            "⏳ Уже думаю над вашим вопросом... Подождите немного!",
            reply_markup=main_keyboard()
        )

    # Определяем текст для AI (кнопка или обычный вопрос)
    user_message = handler if isinstance(handler, str) else text

    # Помечаем как занятый
    pending.add(chat_id)

    # Показываем "печатает..."
    await bot.send_chat_action(chat_id, "typing")
    loading = await message.answer("⏳ Думаю...", reply_markup=main_keyboard())

    try:
        history = get_history(chat_id)
        answer = await ask_openrouter(history, user_message)

        # Перехват неуверенности ИИ или маркера FALLBACK
        lowered_answer = answer.lower()
        if "[fallback]" in lowered_answer or "не знаю" in lowered_answer or "к сожалению" in lowered_answer:
            answer = (
                "😊 Я ещё учусь и не знаю точного ответа на этот вопрос.\n\n"
                "Но вы можете связаться напрямую с нашим менеджером — он с радостью вам поможет:\n\n"
                "💬 *WhatsApp:* [Написать менеджеру](https://wa.me/996500431430)\n"
                "✈️ *Telegram:* @codify_community (https://t.me/codify_community)\n"
                "📞 *Телефоны:* +996 500 431 430, +996 700 431 430"
            )

        # Сохраняем в историю
        add_to_history(chat_id, "user", user_message)
        add_to_history(chat_id, "model", answer)

        # Удаляем "Думаю..."
        try:
            await bot.delete_message(chat_id, loading.message_id)
        except Exception:
            pass

        await message.answer(answer, parse_mode="Markdown",
                             reply_markup=main_keyboard(),
                             disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error for chat {chat_id}: {e}")

        try:
            await bot.delete_message(chat_id, loading.message_id)
        except Exception:
            pass

        phone = SCHOOL_DATA["phone"]
        phone2 = SCHOOL_DATA["phone2"]
        if "API" in str(e) or "key" in str(e).lower():
            err_text = f"⚙️ Проблема с подключением к AI. Обратитесь к менеджеру напрямую:\n💬 WhatsApp: https://wa.me/996500431430\n✈️ Telegram: @codify_community\n📞 {phone}, {phone2}"
        elif "429" in str(e) or "quota" in str(e).lower():
            err_text = f"😅 Слишком много запросов. Подождите минуту или напишите менеджеру:\n💬 WhatsApp: https://wa.me/996500431430\n✈️ Telegram: @codify_community\n📞 {phone}, {phone2}"
        else:
            err_text = f"❌ Произошла ошибка. Попробуйте позже или напишите менеджеру:\n💬 WhatsApp: https://wa.me/996500431430\n✈️ Telegram: @codify_community\n📞 {phone}, {phone2}"

        await message.answer(err_text, reply_markup=main_keyboard(), disable_web_page_preview=True)

    finally:
        pending.discard(chat_id)


# ===================================================
# ЗАПУСК
# ===================================================
async def main():
    logger.info("🤖 Запускаю Codify Bot...")
    logger.info(f"📚 Школа: {SCHOOL_DATA['name']}")
    logger.info(f"📞 Контакт 1: {SCHOOL_DATA['phone']}")
    logger.info(f"📞 Контакт 2: {SCHOOL_DATA['phone2']}")
    logger.info("✅ Бот запущен! Ожидаю сообщений...\n")

    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
