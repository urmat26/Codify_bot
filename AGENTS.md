# AGENTS.md

## Проект

Telegram-бот IT-школы Codify на **aiogram 3.x** + **Groq** (llama-3.3-70b-versatile). Единственная папка — `telegram-bot/`.

## Запуск

```powershell
cd telegram-bot; python bot.py
```

Перед запуском — скопировать `.env.example` → `.env` и вписать ключи. `.env` в `.gitignore`, не коммитится.

## Архитектура

- **`bot.py`** — точка входа, aiogram Dispatcher, хендлеры (команды, текст, callback)
- **`answers.py`** — 12 готовых ответов для частых тем. Кнопки inline-клавиатуры (`MAIN_KEYBOARD`) возвращают их без вызова AI
- **`ai.py`** — мульти-провайдер: Groq → Gemini (если `GEMINI_API_KEY` есть в `.env`). Ротация Groq-ключей при RateLimitError: `GROQ_API_KEY`, `GROQ_API_KEY_2`, ...
- **`config.py`** — модель, лимиты, тексты сообщений
- **`prompts.py`** — system prompt (~3.8 KB, компактная hand-written выжимка, не `json.dumps`)
- **`session.py`** — in-memory история диалогов (max 10 сообщений)
- **`cache.py`** — in-memory кэш вопрос→ответ
- **`school_data.py`** — **dead code**, не импортируется нигде

## Важные детали

- Команды обрабатываются без AI через **`ANSWERS_MAP`** в `bot.py:55-68`. Свободный текст → `handle_message` → AI
- При старте **`_kill_previous()`** убивает прошлый процесс через `bot.lock` (PID-файл), иначе TelegramConflictError
- AI-запрос синхронный через `groq` SDK (без asyncio, обёрнут в async def)
- Competing keyboard: `MAIN_KEYBOARD` приаттачена к каждому ответу, меню команд `/` удалено (не используется `set_my_commands`)

## Лимиты

- Groq: 30 req/min + 100K tokens/day на ключ. При исчерпании — ротация на след. ключ или Gemini (если настроен)
- Gemini: 60 req/min, тоже может выдать 429. Если все провайдеры упали — `QUOTA_MESSAGE` из `config.py`
