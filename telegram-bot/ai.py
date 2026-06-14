import os
import time
import logging
from groq import Groq, RateLimitError
from config import MODEL, MAX_TOKENS, TEMPERATURE

logger = logging.getLogger(__name__)

_groq_clients: list[Groq] | None = None
_gemini_model = None
_groq_key_index = 0

def _get_groq_keys() -> list[str]:
    keys = []
    primary = os.getenv("GROQ_API_KEY")
    if primary:
        keys.append(primary)
    for i in range(2, 10):
        key = os.getenv(f"GROQ_API_KEY_{i}")
        if key:
            keys.append(key)
    return keys

def _get_groq_clients() -> list[Groq]:
    global _groq_clients
    if _groq_clients is None:
        _groq_clients = [Groq(api_key=k) for k in _get_groq_keys()]
    return _groq_clients

def _next_groq_key() -> None:
    global _groq_key_index
    clients = _get_groq_clients()
    if clients:
        _groq_key_index = (_groq_key_index + 1) % len(clients)
        logger.info("Switched to Groq key %d/%d", _groq_key_index + 1, len(clients))

def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        key = os.getenv("GEMINI_API_KEY")
        if key:
            import google.generativeai as genai
            genai.configure(api_key=key)
            _gemini_model = genai.GenerativeModel("gemini-2.0-flash")
    return _gemini_model


def _groq_available() -> bool:
    return len(_get_groq_clients()) > 0

def _gemini_available() -> bool:
    try:
        return _get_gemini() is not None
    except ImportError:
        return False


def _format_gemini_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
    system_prompt = None
    gemini_history = []
    for msg in messages:
        role = msg["role"]
        content = msg["content"]
        if role == "system":
            system_prompt = content
        elif role == "user":
            gemini_history.append({"role": "user", "parts": [{"text": content}]})
        elif role == "assistant":
            gemini_history.append({"role": "model", "parts": [{"text": content}]})
    return system_prompt, gemini_history


async def _ask_groq(messages: list[dict]) -> str:
    global _groq_key_index
    clients = _get_groq_clients()
    if not clients:
        raise RuntimeError("No Groq API keys configured")

    last_error = None
    for key_try in range(len(clients)):
        client = clients[_groq_key_index]
        for attempt in range(3):
            try:
                resp = client.chat.completions.create(
                    model=MODEL,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                )
                return resp.choices[0].message.content
            except RateLimitError as e:
                last_error = e
                logger.warning("Groq key %d: rate limit (attempt %d/3): %s", _groq_key_index + 1, attempt + 1, e)
                if attempt < 2:
                    time.sleep(3)
                else:
                    _next_groq_key()
            except Exception as e:
                last_error = e
                logger.error("Groq key %d: error (attempt %d/3): %s", _groq_key_index + 1, attempt + 1, e)
                if attempt < 2:
                    time.sleep(1)
                else:
                    _next_groq_key()

    raise last_error or RuntimeError("All Groq keys exhausted")


async def _ask_gemini(messages: list[dict]) -> str:
    model = _get_gemini()
    if not model:
        raise RuntimeError("GEMINI_API_KEY not configured")

    system_prompt, gemini_messages = _format_gemini_messages(messages)

    for attempt in range(3):
        try:
            if system_prompt and gemini_messages:
                user_msg = gemini_messages[-1]
                history = gemini_messages[:-1]
                resp = model.generate_content(
                    user_msg["parts"][0]["text"],
                    generation_config={"max_output_tokens": MAX_TOKENS, "temperature": TEMPERATURE},
                )
            elif gemini_messages:
                resp = model.generate_content(
                    gemini_messages[-1]["parts"][0]["text"],
                    generation_config={"max_output_tokens": MAX_TOKENS, "temperature": TEMPERATURE},
                )
            else:
                raise ValueError("No user messages to send to Gemini")

            return resp.text
        except Exception as e:
            error_lower = str(e).lower()
            if "quota" in error_lower or "429" in error_lower or "rate" in error_lower or "resource exhausted" in error_lower:
                logger.warning("Gemini: quota exhausted (attempt %d/3): %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(3)
                else:
                    raise
            else:
                logger.error("Gemini: error (attempt %d/3): %s", attempt + 1, e)
                if attempt < 2:
                    time.sleep(1)
                else:
                    raise


async def ask_ai(messages: list[dict]) -> str:
    errors = []

    if _groq_available():
        try:
            return await _ask_groq(messages)
        except Exception as e:
            logger.warning("Groq failed, trying next provider: %s", e)
            errors.append(("groq", e))
    else:
        errors.append(("groq", "API key not configured"))

    if _gemini_available():
        try:
            return await _ask_gemini(messages)
        except Exception as e:
            logger.warning("Gemini failed, trying next provider: %s", e)
            errors.append(("gemini", e))
    else:
        errors.append(("gemini", "API key not configured"))

    raise RuntimeError(f"All AI providers failed: {errors}")
