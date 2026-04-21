"""
LinkedIn scraper using Scrapling StealthyFetcher.
No API key required. Uses browser automation with anti-bot stealth.

Playwright blocks the main asyncio event loop when run with await directly.
To avoid this, the entire fetch runs in a dedicated thread with its own
event loop, isolated from the FastAPI/uvicorn loop.
"""
import asyncio
import logging
import re
from concurrent.futures import ThreadPoolExecutor

from scrapling.fetchers import StealthyFetcher

logger = logging.getLogger(__name__)

# One executor shared across requests — Playwright browser instances are expensive
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="linkedin-")

LINKEDIN_TIMEOUT = 40.0  # hard wall-clock cap for the whole operation


def _parse_page(page, company_name: str, url: str) -> dict:
    """Extract data from a Scrapling page object (runs in thread)."""
    name = page.css("h1::text").get("").strip()
    tagline = page.css("p.org-top-card-summary__tagline::text").get("").strip()

    about = (
        page.css(".org-about-us-organization-description__text::text").get("") or
        page.css("section.about-us p::text").get("") or
        page.css("p[data-test-id='about-us__description']::text").get("") or
        tagline
    ).strip()

    website = page.css(
        "a.link-without-visited-state[data-tracking-control-name='org-page_website_link']::attr(href)"
    ).get()

    info_items = [t.strip() for t in page.css(
        ".org-top-card-summary-info-list__info-item::text"
    ).getall() if t.strip()]
    industry = info_items[0] if info_items else None
    headquarters = info_items[1] if len(info_items) > 1 else None
    company_type = info_items[2] if len(info_items) > 2 else None

    specialties_raw = page.css(".org-about-company-module__specialities::text").get("").strip()
    services = [s.strip() for s in specialties_raw.split(",") if s.strip()]

    employee_text = (
        page.css("a[data-control-name='page_member_count']::text").get("") or
        page.css("span.org-top-card-summary-info-list__info-item a::text").get("") or ""
    )
    employee_count = None
    match = re.search(r"([\d,]+)", employee_text.replace(",", ""))
    if match:
        try:
            employee_count = int(match.group(1))
        except ValueError:
            pass

    return {
        "source": "linkedin",
        "status": "success",
        "data": {
            "company_name": name or company_name,
            "description": about or None,
            "website": website,
            "industry": industry or None,
            "headquarters": headquarters or None,
            "company_type": company_type or None,
            "employee_count": employee_count,
            "services": services,
            "linkedin_url": url,
        },
    }


def _fetch_sync(company_name: str, url: str) -> dict:
    """
    Run StealthyFetcher in a brand-new event loop inside a thread.
    This isolates Playwright from the main uvicorn event loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        page = loop.run_until_complete(
            StealthyFetcher.async_fetch(
                url,
                headless=True,
                hide_canvas=True,
                block_webrtc=True,
                network_idle=False,       # LinkedIn fires infinite analytics
                disable_resources=True,   # skip fonts/images for speed
                timeout=25000,
            )
        )
        if page.status != 200:
            return {"source": "linkedin", "status": "no_data", "data": None}
        return _parse_page(page, company_name, url)
    except Exception as e:
        logger.warning("LinkedIn thread scrape error for '%s': %s", company_name, e)
        return {"source": "linkedin", "status": "failed", "error": str(e), "data": None}
    finally:
        try:
            loop.close()
        except Exception:
            pass
        asyncio.set_event_loop(None)


async def scrape(company_name: str) -> dict:
    # Build LinkedIn slug (strip legal suffixes first)
    clean = re.sub(
        r",?\s*(inc\.?|llc\.?|ltd\.?|corp\.?|co\.?|gmbh|ag|s\.a\.?|plc\.?)$",
        "",
        company_name,
        flags=re.IGNORECASE,
    ).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", clean.lower()).strip("-")
    url = f"https://www.linkedin.com/company/{slug}"

    main_loop = asyncio.get_running_loop()
    try:
        result = await asyncio.wait_for(
            main_loop.run_in_executor(_executor, _fetch_sync, company_name, url),
            timeout=LINKEDIN_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        logger.warning("LinkedIn scrape timed out for '%s'", company_name)
        return {"source": "linkedin", "status": "failed", "error": "timeout", "data": None}
    except Exception as e:
        logger.warning("LinkedIn scrape error for '%s': %s", company_name, e)
        return {"source": "linkedin", "status": "failed", "error": str(e), "data": None}
