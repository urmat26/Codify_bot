import os

# Простой парсер .env файла
env = {}
try:
    with open(".env", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split("=", 1)
                if len(parts) == 2:
                    env[parts[0].strip()] = parts[1].strip()
except Exception:
    pass

BOT_TOKEN = env.get("BOT_TOKEN")

OPENROUTER_API_KEY = env.get("OPENROUTER_API_KEY")
OPENROUTER_MODEL = env.get("OPENROUTER_MODEL")
OPENROUTER_API_URL = env.get("OPENROUTER_API_URL")

# Лимит пар сообщений в истории (user + bot = 1 пара)
MAX_HISTORY_PAIRS = 5

