# AGENTS.md

## Project

Telegram-бот IT-школы Codify на **aiogram 3.x** + **Groq** (llama-3.3-70b-versatile). Весь код — в папке `telegram-bot/`.

## Запуск

```powershell
cd telegram-bot; python bot.py
```

Перед запуском — скопировать `.env.example` → `.env` и вписать ключи. `.env` в `.gitignore`, не коммитится.

## Архитектура

- **`bot.py`** — точка входа, aiogram Dispatcher, хендлеры (команды, текст, callback), FSM записи
- **`answers.py`** — 12 готовых ответов для частых тем. Кнопки возвращают их без вызова AI
- **`ai.py`** — мульти-провайдер: Groq (ротация ключей) → Gemini (если `GEMINI_API_KEY` есть). Ротация при RateLimitError
- **`config.py`** — BOT_NAME, модель, лимиты, тексты сообщений
- **`prompts.py`** — system prompt (~4.9 KB, hand-written)
- **`session.py`** — in-memory история диалогов (max 10 сообщений)
- **`cache.py`** — in-memory кэш вопрос→ответ
- **`school_data.py`** в корне — **dead code**, не импортируется (данные вручную в prompts.py)

## Клавиатура

- **ReplyKeyboard** (persistent) — основная навигация: 5 рядов (`📅 Расписание`, `💰 Цены`, `📍 Адрес`, `✏️ Записаться`, `📚 Курсы`, `👦 Возраст`, `🪙 CodeCoin`, `📞 Контакты`, `🔄 Новый чат`)
- **InlineKeyboard** — ссылки (WhatsApp, карты, Instagram, сайт) под ответами

## Важные детали

- При старте **`_kill_previous()`** убивает прошлый процесс через `bot.lock`
- AI-запрос синхронный через `groq` SDK (обёрнут в async def)
- `pending: set[int]` блокирует дублирующиеся запросы
- `MANAGER_CHAT_ID` — уведомления о заявках в Telegram

## Файлы

- `telegram-bot/` — весь код бота
- `school_data.py` — структурированные данные школы (не импортируется)
- `AGENTS.md` — инструкция для OpenCode-сессий
