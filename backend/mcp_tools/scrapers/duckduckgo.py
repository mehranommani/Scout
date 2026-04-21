"""
DuckDuckGo scraper — 3 targeted searches run sequentially.

Runs 3 searches per company in sequence to avoid Python 3.12
asyncio-threading issues that cause silent hangs with concurrent
executor futures. At ~2s per search this adds ~6s total.

Search categories:
  1. General  — overview, founding, industry, HQ
  2. Financial — revenue, funding, investors, valuation
  3. Contact   — email, phone, address, support
"""
import logging
from ddgs import DDGS

logger = logging.getLogger(__name__)

MAX_RESULTS_PER_QUERY = 3   # 3 × 3 categories = 9 total snippets max


def _search(query: str) -> list[dict]:
    """Synchronous DDG text search."""
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=MAX_RESULTS_PER_QUERY))
    except Exception as e:
        logger.warning("DDG search error: %s", e)
        return []


async def scrape(company_name: str) -> dict:
    """
    Run 3 DDG searches sequentially.
    Calling _search synchronously is acceptable because:
    - Each call takes ~1-2s
    - Research is a background task (not latency-sensitive)
    - Avoids all asyncio/threading complexity
    """
    queries = {
        "general":   f'"{company_name}" company overview founded headquarters industry',
        "financial": f'"{company_name}" revenue funding raised investors series valuation 2024 2025',
        "contact":   f'"{company_name}" contact email phone address support',
    }

    all_snippets: list[str] = []
    all_urls: list[str] = []
    financial_snippets: list[str] = []
    contact_snippets: list[str] = []

    for category, query in queries.items():
        try:
            results = _search(query)
        except Exception as e:
            logger.warning("DDG '%s' search failed: %s", category, e)
            results = []

        for r in results:
            body = r.get("body", "").strip()
            url = r.get("href", "").strip()
            if not body:
                continue
            labelled = f"[{category.upper()}] {body}"
            all_snippets.append(labelled)
            if url:
                all_urls.append(url)
            if category == "financial":
                financial_snippets.append(body)
            elif category == "contact":
                contact_snippets.append(body)

    if not all_snippets:
        return {"source": "duckduckgo", "status": "no_data", "data": None}

    return {
        "source": "duckduckgo",
        "status": "success",
        "data": {
            "company_name": company_name,
            "raw_snippets": all_snippets,
            "financial_snippets": financial_snippets,
            "contact_snippets": contact_snippets,
            "urls": all_urls,
            "website": all_urls[0] if all_urls else None,
            "description": None,
            "founders": [],
            "industry": None,
        },
    }
