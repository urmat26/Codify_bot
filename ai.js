const fetch = require("node-fetch");
const { CONFIG } = require("./config");
const { buildSystemPrompt } = require("./prompts");

// ===================================================
// AI MODULE — Gemini API
// ===================================================

/**
 * Отправляет сообщение в Gemini AI и возвращает ответ
 * @param {Array} history — история диалога [{ role: 'user'|'model', parts: [{text}] }]
 * @param {string} userMessage — новое сообщение пользователя
 * @returns {Promise<string>} — ответ бота
 */
async function askGemini(history, userMessage) {
  const systemPrompt = buildSystemPrompt();

  // Формируем содержимое для отправки
  const contents = [
    // История сообщений (только последние MAX_HISTORY_PAIRS пар)
    ...history.slice(-CONFIG.MAX_HISTORY_PAIRS * 2),
    // Новое сообщение пользователя
    {
      role: "user",
      parts: [{ text: userMessage }],
    },
  ];

  const requestBody = {
    system_instruction: {
      parts: [{ text: systemPrompt }],
    },
    contents: contents,
    generationConfig: {
      temperature: 0.3,
      maxOutputTokens: 600,
      topP: 0.8,
    },
    safetySettings: [
      {
        category: "HARM_CATEGORY_HARASSMENT",
        threshold: "BLOCK_ONLY_HIGH",
      },
      {
        category: "HARM_CATEGORY_HATE_SPEECH",
        threshold: "BLOCK_ONLY_HIGH",
      },
    ],
  };

  const url = `${CONFIG.GEMINI_API_URL}?key=${CONFIG.GEMINI_API_KEY}`;

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(requestBody),
    timeout: CONFIG.RESPONSE_TIMEOUT,
  });

  if (!response.ok) {
    const errorText = await response.text();
    console.error("Gemini API error:", response.status, errorText);
    throw new Error(`Gemini API error: ${response.status}`);
  }

  const data = await response.json();

  // Извлекаем текст ответа
  const candidate = data.candidates?.[0];
  if (!candidate || !candidate.content?.parts?.[0]?.text) {
    throw new Error("No valid response from Gemini");
  }

  return candidate.content.parts[0].text.trim();
}

module.exports = { askGemini };
