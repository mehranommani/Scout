"""
Wikidata SPARQL scraper — free, no API key.
Uses the public SPARQL endpoint at https://query.wikidata.org/sparql

Fields fetched:
  - Basic: name, description, inception, website, industry, country, HQ location
  - Contact: email (P968), phone (P1329), address (P6375)
  - Staff: historical founders (P112), current CEO (P169)
  - Financial: annual revenue (P2139), total assets (P2403), employees (P1128)

Note on founders (P112): Wikidata stores ALL historical founders.
We label them "historical_founder" so downstream code can distinguish
from current leadership (CEO from P169).
"""
import re
import httpx
import logging

logger = logging.getLogger(__name__)


def _name_variants(company_name: str) -> list[str]:
    """
    Generate name variants to try against Wikidata labels.
    Wikidata often stores the short name ('Stripe') rather than the
    legal entity name ('Stripe, Inc.'). Try both.
    """
    variants = [company_name]
    # Strip common legal suffixes
    stripped = re.sub(
        r",?\s*(inc\.?|llc\.?|ltd\.?|corp\.?|co\.?|gmbh|ag|s\.a\.?|plc\.)$",
        "",
        company_name,
        flags=re.IGNORECASE,
    ).strip()
    if stripped and stripped.lower() != company_name.lower():
        variants.append(stripped)
    return variants


def _safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


SPARQL_URL = "https://query.wikidata.org/sparql"

# Two separate queries to avoid combinatorial explosion:
#   Query A — core company data + founders + CEO
#   Query B — contact / address fields
QUERY_CORE = """
SELECT DISTINCT ?company ?companyLabel ?description ?inception ?website
       ?industryLabel ?employeeCount ?revenue ?totalAssets
       ?founderLabel ?ceoLabel ?countryLabel ?hqLabel
WHERE {{
  ?company rdfs:label "{name}"@en .
  ?company wdt:P31/wdt:P279* wd:Q4830453 .
  OPTIONAL {{ ?company schema:description ?description FILTER(LANG(?description) = "en") }}
  OPTIONAL {{ ?company wdt:P571 ?inception }}
  OPTIONAL {{ ?company wdt:P856 ?website }}
  OPTIONAL {{ ?company wdt:P452 ?industry }}
  OPTIONAL {{ ?company wdt:P1128 ?employeeCount }}
  OPTIONAL {{ ?company wdt:P2139 ?revenue }}
  OPTIONAL {{ ?company wdt:P2403 ?totalAssets }}
  OPTIONAL {{ ?company wdt:P112 ?founder }}
  OPTIONAL {{ ?company wdt:P169 ?ceo }}
  OPTIONAL {{ ?company wdt:P17 ?country }}
  OPTIONAL {{ ?company wdt:P159 ?hq }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
LIMIT 10
"""

QUERY_CONTACT = """
SELECT DISTINCT ?company ?email ?phone ?streetAddress
WHERE {{
  ?company rdfs:label "{name}"@en .
  ?company wdt:P31/wdt:P279* wd:Q4830453 .
  OPTIONAL {{ ?company wdt:P968 ?email }}
  OPTIONAL {{ ?company wdt:P1329 ?phone }}
  OPTIONAL {{ ?company wdt:P6375 ?streetAddress }}
}}
LIMIT 5
"""


async def _run_query(client: httpx.AsyncClient, query: str, headers: dict) -> list[dict]:
    resp = await client.post(SPARQL_URL, data={"query": query}, headers=headers)
    resp.raise_for_status()
    return resp.json().get("results", {}).get("bindings", [])


async def scrape(company_name: str) -> dict:
    headers = {
        "Accept": "application/sparql-results+json",
        "User-Agent": "ScoutResearchBot/1.0 (https://github.com/scout-agent)",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        async with httpx.AsyncClient(timeout=25) as client:
            core_bindings: list[dict] = []
            tried_name = company_name.replace('"', '\\"')
            for variant in _name_variants(company_name):
                escaped = variant.replace('"', '\\"')
                core_bindings = await _run_query(client, QUERY_CORE.format(name=escaped), headers)
                if core_bindings:
                    tried_name = escaped
                    break

            try:
                contact_bindings = await _run_query(client, QUERY_CONTACT.format(name=tried_name), headers)
            except Exception:
                contact_bindings = []

        if not core_bindings:
            return {"source": "wikidata", "status": "no_data", "data": None}

        b = core_bindings[0]

        def val(key: str) -> str | None:
            return b[key]["value"] if key in b else None

        # Collect ALL historical founders (deduplicated)
        historical_founders = list({
            row["founderLabel"]["value"]
            for row in core_bindings
            if "founderLabel" in row
        })

        # Collect current CEOs (deduplicated, may differ from founders)
        current_ceos = list({
            row["ceoLabel"]["value"]
            for row in core_bindings
            if "ceoLabel" in row
        })

        # Contact fields from the second query
        contact: dict[str, str] = {}
        for cb in contact_bindings:
            if "email" in cb and "email" not in contact:
                contact["email"] = cb["email"]["value"]
            if "phone" in cb and "phone" not in contact:
                contact["phone"] = cb["phone"]["value"]
            if "streetAddress" in cb and "address" not in contact:
                contact["address"] = cb["streetAddress"]["value"]

        return {
            "source": "wikidata",
            "status": "success",
            "data": {
                "company_name": val("companyLabel"),
                "description": val("description"),
                "founded_date": val("inception"),
                "website": val("website"),
                "industry": val("industryLabel"),
                "employee_count": _safe_int(val("employeeCount")),
                "revenue_usd": _safe_int(val("revenue")),
                "total_assets_usd": _safe_int(val("totalAssets")),
                "jurisdiction": val("countryLabel"),
                "headquarters": val("hqLabel"),
                "wikidata_url": val("company"),
                # Founders labelled explicitly as historical (P112 = all-time)
                "historical_founders": [{"name": f, "role": "Historical Founder"} for f in historical_founders],
                # Current leadership from P169 (CEO)
                "current_leadership": [{"name": c, "role": "CEO"} for c in current_ceos],
                "contact": contact,
            },
        }
    except httpx.HTTPStatusError as e:
        logger.warning("Wikidata HTTP error: %s", e)
        return {"source": "wikidata", "status": "failed", "error": str(e), "data": None}
    except Exception as e:
        logger.warning("Wikidata error: %s", e)
        return {"source": "wikidata", "status": "failed", "error": str(e), "data": None}
