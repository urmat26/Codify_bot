import logging

logger = logging.getLogger(__name__)

_cache: dict[str, str] = {}

def cache_get(question: str) -> str | None:
    key = question.lower().strip()
    return _cache.get(key)

def cache_set(question: str, answer: str) -> None:
    key = question.lower().strip()
    if key not in _cache:
        logger.info("Cache set for: %r", key[:60])
    _cache[key] = answer

def cache_clear() -> None:
    _cache.clear()
