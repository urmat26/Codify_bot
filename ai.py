import aiohttp
from config import OPENROUTER_API_KEY, OPENROUTER_API_URL, OPENROUTER_MODEL
from prompts import build_system_prompt
import logging

# ===================================================
# OPENROUTER AI MODULE
# ===================================================

logger = logging.getLogger(__name__)

async def ask_openrouter(history: list, user_message: str) -> str:
    """
    Отправляет запрос в OpenRouter API и возвращает ответ бота.
    
    history: список словарей [{"role": "user"|"model", "parts": [{"text": "..."}]}]
    user_message: новое сообщение пользователя
    """
    system_prompt = build_system_prompt()

    # Берём только последние MAX_HISTORY_PAIRS пар
    from config import MAX_HISTORY_PAIRS
    recent_history = history[-(MAX_HISTORY_PAIRS * 2):]

    # Преобразуем историю в формат OpenAI/OpenRouter
    messages = [{"role": "system", "content": system_prompt}]
    for item in recent_history:
        role = "user" if item.get("role") == "user" else "assistant"
        # Безопасное извлечение текста
        text = ""
        if "parts" in item and len(item["parts"]) > 0:
            text = item["parts"][0].get("text", "")
        elif "content" in item:
            text = item["content"]
        messages.append({"role": role, "content": text})

    # Добавляем новое сообщение
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1000
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/urmat26/Codify_bot",
        "X-Title": "Codify Bot"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_API_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 429:
                logger.warning('OpenRouter quota exceeded / rate limited')
                return "[FALLBACK]"
            if resp.status != 200:
                error_text = await resp.text()
                raise Exception(f"OpenRouter API error {resp.status}: {error_text[:200]}")

            data = await resp.json()

    # Извлекаем текст ответа
    try:
        answer = data["choices"][0]["message"]["content"]
        return answer.strip()
    except (KeyError, IndexError) as e:
        raise Exception(f"Unexpected OpenRouter response structure: {e}")

