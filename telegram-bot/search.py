import asyncio
import logging
from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)


async def web_search(query: str, max_results: int = 5) -> list[str]:
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None, lambda: list(DDGS().text(query, max_results=max_results))
        )
        snippets = []
        for r in results:
            title = r.get("title", "")
            body = r.get("body", "")
            link = r.get("href", "")
            if body:
                snippets.append(f"• {title}: {body.strip()[:300]} ({link})")
        return snippets
    except Exception as e:
        logger.warning("Web search failed for '%s': %s", query, e)
        return []
