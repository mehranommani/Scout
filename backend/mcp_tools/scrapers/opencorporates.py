"""
OpenCorporates scraper — free public REST API.
Docs: https://api.opencorporates.com/documentation/API-Reference
"""
import httpx
import logging

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.opencorporates.com/v0.4"


async def scrape(company_name: str) -> dict:
    """Search OpenCorporates for a company and return normalised data."""
    params: dict = {"q": company_name, "format": "json", "per_page": "3"}
    if settings.OPENCORPORATES_API_KEY:
        params["api_token"] = settings.OPENCORPORATES_API_KEY

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/companies/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        companies = data.get("results", {}).get("companies", [])
        if not companies:
            return {"source": "opencorporates", "status": "no_data", "data": None}

        # Pick the best match — first result
        company = companies[0]["company"]
        return {
            "source": "opencorporates",
            "status": "success",
            "data": {
                "company_name": company.get("name"),
                "jurisdiction": company.get("jurisdiction_code"),
                "registration_number": company.get("company_number"),
                "founded_date": company.get("incorporation_date"),
                "website": company.get("registered_address", {}).get("street_address") if isinstance(company.get("registered_address"), dict) else None,
                "contact": {
                    "address": company.get("registered_address", {}).get("street_address") if isinstance(company.get("registered_address"), dict) else None,
                },
                "industry": company.get("industry_codes", [{}])[0].get("description") if company.get("industry_codes") else None,
                "opencorporates_url": company.get("opencorporates_url"),
            },
        }
    except httpx.HTTPStatusError as e:
        logger.warning("OpenCorporates HTTP error: %s", e)
        return {"source": "opencorporates", "status": "failed", "error": str(e), "data": None}
    except Exception as e:
        logger.warning("OpenCorporates error: %s", e)
        return {"source": "opencorporates", "status": "failed", "error": str(e), "data": None}
