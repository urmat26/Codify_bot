from .env imoprt BOT_TOKEN, GEMINI_API_KEY, GEMINI_MODEL, GEMINI_API_URL

// ===================================================
// КОНФИГУРАЦИЯ БОТА
// ===================================================

const CONFIG = {
  // Telegram Bot Token
  BOT_TOKEN: "BOT_TOKEN",

  // Gemini API Key — ВСТАВЬ СВОЙ КЛЮЧ СЮДА
  GEMINI_API_KEY: "GEMINI_API_KEY",

  // Настройки Gemini
  GEMINI_MODEL: "GEMINI_MODEL",
  GEMINI_API_URL: "GEMINI_API_URL",

  // Лимит истории сообщений (последних N пар user/bot)
  MAX_HISTORY_PAIRS: 5,

  // Таймаут ожидания ответа (мс)
  RESPONSE_TIMEOUT: 30000,
};

module.exports = { CONFIG };
