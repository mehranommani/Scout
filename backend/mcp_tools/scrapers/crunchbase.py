"""
Crunchbase scraper — uses the official REST API v4.
Requires CRUNCHBASE_API_KEY in .env; skipped automatically when blank.
Docs: https://data.crunchbase.com/docs
"""
import httpx
import logging

from config import settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.crunchbase.com/api/v4"


async def scrape(company_name: str) -> dict:
    if not settings.CRUNCHBASE_API_KEY:
        return {"source": "crunchbase", "status": "skipped", "error": "No API key", "data": None}

    # Step 1: autocomplete search to get the permalink
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            search_resp = await client.get(
                f"{BASE_URL}/autocompletes",
                params={
                    "query": company_name,
                    "collection_ids": "organizations",
                    "limit": "3",
                    "user_key": settings.CRUNCHBASE_API_KEY,
                },
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()

        entities = search_data.get("entities", [])
        if not entities:
            return {"source": "crunchbase", "status": "no_data", "data": None}

        permalink = entities[0].get("identifier", {}).get("permalink")
        if not permalink:
            return {"source": "crunchbase", "status": "no_data", "data": None}

        # Step 2: fetch full org details
        fields = ",".join([
            "short_description", "founded_on", "website_url", "linkedin",
            "num_employees_enum", "total_funding_usd", "revenue_range",
            "category_list", "location_identifiers", "founder_identifiers",
        ])
        async with httpx.AsyncClient(timeout=15) as client:
            detail_resp = await client.get(
                f"{BASE_URL}/entities/organizations/{permalink}",
                params={"field_ids": fields, "user_key": settings.CRUNCHBASE_API_KEY},
            )
            detail_resp.raise_for_status()
            detail = detail_resp.json().get("properties", {})

        founders = [
            {"name": f.get("value"), "role": "Founder"}
            for f in detail.get("founder_identifiers", [])
            if f.get("value")
        ]

        location = detail.get("location_identifiers", [])
        country = next((l["value"] for l in location if l.get("location_type") == "country"), None)

        return {
            "source": "crunchbase",
            "status": "success",
            "data": {
                "company_name": entities[0].get("identifier", {}).get("value"),
                "description": detail.get("short_description"),
                "founded_date": detail.get("founded_on", {}).get("value") if isinstance(detail.get("founded_on"), dict) else detail.get("founded_on"),
                "website": detail.get("website_url"),
                "linkedin_url": detail.get("linkedin", {}).get("value") if isinstance(detail.get("linkedin"), dict) else None,
                "total_funding_usd": detail.get("total_funding_usd"),
                "industry": ", ".join([c.get("value", "") for c in detail.get("category_list", [])]),
                "founders": founders,
                "jurisdiction": country,
                "crunchbase_url": f"https://www.crunchbase.com/organization/{permalink}",
            },
        }
    except httpx.HTTPStatusError as e:
        logger.warning("Crunchbase HTTP error: %s", e)
        return {"source": "crunchbase", "status": "failed", "error": str(e), "data": None}
    except Exception as e:
        logger.warning("Crunchbase error: %s", e)
        return {"source": "crunchbase", "status": "failed", "error": str(e), "data": None}
