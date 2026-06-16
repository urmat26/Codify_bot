const TelegramBot = require("node-telegram-bot-api");
const { CONFIG } = require("./config");
const { askGemini } = require("./ai");
const { SCHOOL_DATA } = require("./school-data");
const { QUICK_REPLIES } = require("./prompts");

// ===================================================
// TELEGRAM BOT — CODIFY ACADEMY
// ===================================================

const bot = new TelegramBot(CONFIG.BOT_TOKEN, { polling: true });

// Хранилище истории чатов: { chatId: [{role, parts}] }
const chatHistories = new Map();

// Хранилище состояний (ожидание ответа AI)
const pendingRequests = new Set();

// ===================================================
// ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
// ===================================================

function getHistory(chatId) {
  if (!chatHistories.has(chatId)) {
    chatHistories.set(chatId, []);
  }
  return chatHistories.get(chatId);
}

function addToHistory(chatId, role, text) {
  const history = getHistory(chatId);
  history.push({
    role: role, // 'user' or 'model'
    parts: [{ text }],
  });
  // Лимит истории
  if (history.length > CONFIG.MAX_HISTORY_PAIRS * 2) {
    history.splice(0, 2);
  }
}

function clearHistory(chatId) {
  chatHistories.set(chatId, []);
}

// ===================================================
// КЛАВИАТУРЫ
// ===================================================

const mainKeyboard = {
  reply_markup: {
    keyboard: [
      [{ text: "📅 Расписание" }, { text: "💰 Цены" }],
      [{ text: "📍 Адрес" }, { text: "✏️ Записаться" }],
      [{ text: "📚 Курсы" }, { text: "👦 Возраст" }],
      [{ text: "💻 Онлайн" }, { text: "🔄 Новый чат" }],
    ],
    resize_keyboard: true,
    persistent: true,
  },
  parse_mode: "HTML",
};

const inlineContactKeyboard = {
  reply_markup: {
    inline_keyboard: [
      [
        {
          text: "📞 Позвонить",
          url: `tel:${SCHOOL_DATA.phone.replace(/\s/g, "")}`,
        },
        {
          text: "💬 WhatsApp",
          url: SCHOOL_DATA.whatsapp,
        },
      ],
      [
        {
          text: "🌐 Сайт Codify",
          url: SCHOOL_DATA.website,
        },
        {
          text: "📸 Instagram",
          url: SCHOOL_DATA.instagram,
        },
      ],
    ],
  },
};

// ===================================================
// КОМАНДЫ
// ===================================================

// /start
bot.onText(/\/start/, async (msg) => {
  const chatId = msg.chat.id;
  const firstName = msg.from.first_name || "друг";

  clearHistory(chatId);

  const welcomeText = `
👋 Привет, <b>${firstName}</b>!

Я <b>Кодик</b> — ассистент IT-школы программирования <b>Codify</b> 🎓

Помогу тебе узнать:
• 📚 Какие курсы есть и для кого
• 📅 Расписание занятий
• 📍 Где находится школа
• 💰 Стоимость обучения
• ✏️ Как записаться

Просто напиши вопрос или нажми кнопку ниже 👇
  `.trim();

  await bot.sendMessage(chatId, welcomeText, {
    ...mainKeyboard,
    parse_mode: "HTML",
  });
});

// /help
bot.onText(/\/help/, async (msg) => {
  const chatId = msg.chat.id;

  const helpText = `
<b>🎓 Как пользоваться ботом Codify:</b>

Просто задай вопрос текстом! Например:
• "Какие курсы есть для детей 10 лет?"
• "Сколько стоит обучение?"
• "Где находится школа?"
• "Как записаться?"

<b>Быстрые кнопки:</b>
📅 <b>Расписание</b> — частота и формат занятий
💰 <b>Цены</b> — стоимость курсов
📍 <b>Адрес</b> — где находимся
✏️ <b>Записаться</b> — как записаться на курс
📚 <b>Курсы</b> — все программы обучения
👦 <b>Возраст</b> — для кого подходит
💻 <b>Онлайн</b> — дистанционное обучение
🔄 <b>Новый чат</b> — очистить историю

<b>Контакты:</b>
📞 ${SCHOOL_DATA.phone}
  `.trim();

  await bot.sendMessage(chatId, helpText, {
    ...mainKeyboard,
    parse_mode: "HTML",
  });
});

// /reset — новый чат
bot.onText(/\/reset/, async (msg) => {
  const chatId = msg.chat.id;
  clearHistory(chatId);
  await bot.sendMessage(chatId, "🔄 История очищена! Начнём сначала. Задай свой вопрос 👇", mainKeyboard);
});

// /contacts — контакты
bot.onText(/\/contacts/, async (msg) => {
  const chatId = msg.chat.id;
  await sendContacts(chatId);
});

// ===================================================
// ФУНКЦИИ ОТПРАВКИ ГОТОВЫХ ОТВЕТОВ
// ===================================================

async function sendContacts(chatId) {
  const text = `
<b>📞 Контакты Codify:</b>

📱 <b>Телефон / WhatsApp / Telegram:</b>
${SCHOOL_DATA.phone}

🌐 <b>Сайт:</b> codifylab.com
📸 <b>Instagram:</b> @codify.kids
📧 <b>Email:</b> ${SCHOOL_DATA.email}
  `.trim();

  await bot.sendMessage(chatId, text, {
    parse_mode: "HTML",
    reply_markup: inlineContactKeyboard.reply_markup,
  });
}

async function sendAddress(chatId) {
  const branches = SCHOOL_DATA.branches;
  let text = `<b>📍 Адреса филиалов Codify в Бишкеке:</b>\n\n`;

  branches.forEach((b, i) => {
    text += `<b>${i + 1}. ${b.name}</b>\n`;
    text += `🏢 ${b.address}`;
    if (b.landmark) text += ` (${b.landmark})`;
    text += `\n`;
    text += `🗺 <a href="${b.maps2gis}">Открыть на 2ГИС</a>\n\n`;
  });

  await bot.sendMessage(chatId, text, {
    parse_mode: "HTML",
    disable_web_page_preview: true,
    reply_markup: {
      inline_keyboard: [
        [
          { text: "🗺 7-й мкр на 2ГИС", url: branches[0].maps2gis },
          { text: "🗺 Ибраимова на 2ГИС", url: branches[1].maps2gis },
        ],
        [{ text: "🗺 Джал на 2ГИС", url: branches[2].maps2gis }],
      ],
    },
  });
}

async function sendCourses(chatId) {
  const courses = SCHOOL_DATA.courses;
  let text = `<b>📚 Курсы Codify — путь из 7 этапов:</b>\n\n`;

  const groups = {
    "7–9 лет": courses.filter((c) => c.ageGroup === "7–9 лет"),
    "10–13 лет": courses.filter((c) => c.ageGroup === "10–13 лет"),
    "14–17 лет": courses.filter((c) => c.ageGroup === "14–17 лет"),
  };

  for (const [age, list] of Object.entries(groups)) {
    text += `<b>👤 ${age}:</b>\n`;
    list.forEach((c) => {
      text += `  • ${c.stage}: <b>${c.name}</b> — ${c.subtitle} (${c.duration})\n`;
    });
    text += "\n";
  }

  text += `✅ Офлайн и онлайн форматы\n`;
  text += `📞 Запись: ${SCHOOL_DATA.phone}`;

  await bot.sendMessage(chatId, text, {
    parse_mode: "HTML",
    reply_markup: {
      inline_keyboard: [
        [{ text: "✏️ Записаться на курс", url: SCHOOL_DATA.whatsapp }],
        [{ text: "🌐 Подробнее на сайте", url: SCHOOL_DATA.website }],
      ],
    },
  });
}

// ===================================================
// ОБРАБОТКА КНОПОК И СООБЩЕНИЙ
// ===================================================

const BUTTON_MAP = {
  "📅 Расписание": QUICK_REPLIES.schedule,
  "💰 Цены": QUICK_REPLIES.prices,
  "📍 Адрес": null, // специальный обработчик
  "✏️ Записаться": QUICK_REPLIES.enroll,
  "📚 Курсы": null, // специальный обработчик
  "👦 Возраст": QUICK_REPLIES.age,
  "💻 Онлайн": QUICK_REPLIES.online,
  "🔄 Новый чат": null, // специальный обработчик
};

bot.on("message", async (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;

  // Игнорируем команды (они обрабатываются отдельно)
  if (!text || text.startsWith("/")) return;

  // Проверка на ожидание ответа
  if (pendingRequests.has(chatId)) {
    await bot.sendMessage(
      chatId,
      "⏳ Уже думаю над вашим вопросом... Подождите немного!",
      { reply_markup: mainKeyboard.reply_markup }
    );
    return;
  }

  // === СПЕЦИАЛЬНЫЕ КНОПКИ ===
  if (text === "📍 Адрес") {
    return await sendAddress(chatId);
  }

  if (text === "📚 Курсы") {
    return await sendCourses(chatId);
  }

  if (text === "🔄 Новый чат") {
    clearHistory(chatId);
    return await bot.sendMessage(
      chatId,
      "🔄 История очищена! Задай новый вопрос 👇",
      mainKeyboard
    );
  }

  // === AI ЗАПРОС ===
  // Определяем текст для AI (кнопка или обычное сообщение)
  let userMessage = text;
  if (BUTTON_MAP[text]) {
    userMessage = BUTTON_MAP[text];
  }

  // Помечаем как ожидание
  pendingRequests.add(chatId);

  // Показываем индикатор печатания
  await bot.sendChatAction(chatId, "typing");

  // Отправляем "Печатаю..." сообщение
  let loadingMsg;
  try {
    loadingMsg = await bot.sendMessage(chatId, "⏳ Думаю...", {
      reply_markup: mainKeyboard.reply_markup,
    });
  } catch (e) {
    console.error("Could not send loading message:", e.message);
  }

  try {
    // Получаем историю
    const history = getHistory(chatId);

    // Запрашиваем AI
    const answer = await askGemini(history, userMessage);

    // Сохраняем в историю
    addToHistory(chatId, "user", userMessage);
    addToHistory(chatId, "model", answer);

    // Удаляем "Думаю..."
    if (loadingMsg) {
      try {
        await bot.deleteMessage(chatId, loadingMsg.message_id);
      } catch (e) {
        // Игнорируем ошибку удаления
      }
    }

    // Отправляем ответ
    await bot.sendMessage(chatId, answer, {
      parse_mode: "HTML",
      reply_markup: mainKeyboard.reply_markup,
      disable_web_page_preview: true,
    });
  } catch (error) {
    console.error(`Error for chat ${chatId}:`, error.message);

    // Удаляем "Думаю..."
    if (loadingMsg) {
      try {
        await bot.deleteMessage(chatId, loadingMsg.message_id);
      } catch (e) {}
    }

    // Определяем тип ошибки
    let errorText;
    if (
      error.message.includes("API_KEY") ||
      error.message.includes("YOUR_GEMINI")
    ) {
      errorText = `⚙️ Бот настраивается. Обратитесь к менеджеру напрямую:\n📞 ${SCHOOL_DATA.phone}`;
    } else if (error.message.includes("quota") || error.message.includes("429")) {
      errorText = `😅 Слишком много запросов. Попробуйте через минуту или свяжитесь с менеджером:\n📞 ${SCHOOL_DATA.phone}`;
    } else {
      errorText = `❌ Произошла ошибка. Попробуйте позже или обратитесь к менеджеру:\n📞 ${SCHOOL_DATA.phone}`;
    }

    await bot.sendMessage(chatId, errorText, {
      reply_markup: mainKeyboard.reply_markup,
    });
  } finally {
    pendingRequests.delete(chatId);
  }
});

// ===================================================
// ОБРАБОТКА ОШИБОК POLLING
// ===================================================

bot.on("polling_error", (error) => {
  console.error("Polling error:", error.message);
});

bot.on("error", (error) => {
  console.error("Bot error:", error.message);
});

// ===================================================
// ЗАПУСК
// ===================================================

console.log("🤖 Codify Bot запущен!");
console.log(`📚 Школа: ${SCHOOL_DATA.name}`);
console.log(`📞 Контакт: ${SCHOOL_DATA.phone}`);
console.log("✅ Ожидаю сообщений...\n");

// Graceful shutdown
process.on("SIGINT", () => {
  console.log("\n🛑 Бот остановлен.");
  bot.stopPolling();
  process.exit(0);
});
