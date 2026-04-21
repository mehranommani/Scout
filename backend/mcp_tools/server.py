"""
FastMCP tool server.
Tools are called in-process by the LangGraph agent (not over HTTP).

FastMCP docs: https://gofastmcp.com
Tool decorator: @mcp.tool  (auto-generates schema from type hints + docstring)

call_tool() returns a ToolResult object.
Use call_tool_data() helper below to extract the plain dict/value directly:
  result.structured_content  → the raw Python return value as a dict
  result.content[0].text     → JSON string fallback
"""
import json
import logging
from fastmcp import FastMCP
from mcp.types import TextContent

from mcp_tools.scrapers import opencorporates, wikidata, crunchbase, linkedin, duckduckgo

logger = logging.getLogger(__name__)

mcp = FastMCP("scout-tools")


async def call_tool_data(name: str, arguments: dict):
    """
    Call an MCP tool in-process and return its plain Python return value.
    FastMCP call_tool() wraps the result in a ToolResult object;
    structured_content holds the original dict/value, falling back to
    parsing the JSON text content.
    """
    result = await mcp.call_tool(name, arguments)
    if result.structured_content is not None:
        return result.structured_content
    if result.content:
        item = result.content[0]
        if isinstance(item, TextContent):
            return json.loads(item.text)
    return None


# ---------------------------------------------------------------------------
# Tool 1: validate_company_name
# Called by classify_input node BEFORE LLM — quick heuristic pre-check.
# ---------------------------------------------------------------------------
@mcp.tool
def validate_name_format(name: str) -> dict:
    """
    Quick heuristic check: is the input plausibly a company/product name?
    Returns {"likely_valid": bool, "reason": str}.
    Does NOT do LLM classification — that happens in the agent node.
    """
    name = name.strip()
    if len(name) < 2:
        return {"likely_valid": False, "reason": "Input too short."}
    if len(name) > 300:
        return {"likely_valid": False, "reason": "Input too long."}
    # Reject inputs that look like plain personal names (First Last, no corporate suffix)
    words = name.split()
    personal_suffixes = {"jr", "sr", "ii", "iii", "iv", "phd", "md", "esq"}
    corporate_hints = {"inc", "llc", "ltd", "corp", "co", "gmbh", "ag", "sa",
                       "group", "technologies", "solutions", "systems", "labs",
                       "services", "holdings", "ventures", "capital"}
    lower_words = {w.lower().strip(".,") for w in words}
    has_corporate = bool(lower_words & corporate_hints)
    # Flag as personal name when: 2-4 words, no corporate suffix, contains a
    # personal suffix (Jr/Sr/PhD/MD/Esq/II/III/IV) OR all words look like names
    # (2 capitalised words with no corporate hints).
    has_personal_suffix = bool(lower_words & personal_suffixes)
    looks_like_two_word_name = (
        len(words) == 2
        and not has_corporate
        and lower_words.isdisjoint({"the", "of", "and", "&"})
        and all(w[0].isupper() for w in words if w)
    )
    if not has_corporate and (has_personal_suffix or looks_like_two_word_name) and len(words) <= 4:
        return {"likely_valid": False, "reason": "Looks like a personal name."}
    return {"likely_valid": True, "reason": "Passes basic format check."}


# ---------------------------------------------------------------------------
# Tool 2: scrape_source  (async — runs all scrapers)
# ---------------------------------------------------------------------------
@mcp.tool
async def scrape_source(company_name: str, source: str) -> dict:
    """
    Scrape a single data source for company information.
    source must be one of: opencorporates, wikidata, crunchbase, linkedin, duckduckgo
    Returns a normalised dict with keys: source, status, data, error.
    """
    source = source.lower().strip()
    dispatch = {
        "opencorporates": opencorporates.scrape,
        "wikidata": wikidata.scrape,
        "crunchbase": crunchbase.scrape,
        "linkedin": linkedin.scrape,
        "duckduckgo": duckduckgo.scrape,
    }
    fn = dispatch.get(source)
    if fn is None:
        return {"source": source, "status": "failed", "error": f"Unknown source: {source}", "data": None}
    return await fn(company_name)


# ---------------------------------------------------------------------------
# Tool 3: merge_source_results
# Aggregates raw scrape results into a single company_data dict.
# ---------------------------------------------------------------------------
@mcp.tool
def merge_source_results(results: list[dict], company_name: str) -> dict:
    """
    Merges raw scrape results from multiple sources into one canonical dict.

    Fields:
      - historical_founders: people who founded the company (all-time, from Wikidata P112)
      - current_leadership: current executives (CEO etc., from Wikidata P169)
      - financial_snippets / contact_snippets: labelled web snippets for targeted sections
      - contact: structured contact dict (email, phone, address)

    Prioritises non-None values; first-seen wins for scalar fields.
    """
    merged: dict = {
        "company_name": company_name,
        "description": None,
        "website": None,
        "linkedin_url": None,
        "industry": None,
        "founded_date": None,
        "jurisdiction": None,
        "headquarters": None,
        # Founders are split: historical (P112) vs current leadership (P169)
        "historical_founders": [],
        "current_leadership": [],
        "services": [],
        "company_type": None,
        "contact": {},           # structured: email, phone, address
        "revenue_usd": None,
        "total_assets_usd": None,
        "total_funding_usd": None,
        "employee_count": None,
        "sources_used": [],
        "raw_snippets": [],          # all labelled snippets
        "financial_snippets": [],    # finance-specific snippets
        "contact_snippets": [],      # contact-specific snippets
    }

    seen_historical: set[str] = set()
    seen_leadership: set[str] = set()

    for result in results:
        if result.get("status") != "success":
            continue
        data = result.get("data") or {}
        src = result.get("source", "")
        merged["sources_used"].append(src)

        # Scalar fields: first non-None wins
        for field in ("description", "website", "linkedin_url", "industry",
                      "founded_date", "jurisdiction", "headquarters",
                      "revenue_usd", "total_assets_usd",
                      "total_funding_usd", "employee_count", "company_type"):
            if merged[field] is None and data.get(field) is not None:
                merged[field] = data[field]

        # Company name: prefer longer/more specific
        if data.get("company_name") and len(str(data["company_name"])) > len(merged["company_name"]):
            merged["company_name"] = data["company_name"]

        # Historical founders (from Wikidata P112) — deduplicate by name
        for f in data.get("historical_founders", []):
            name = f.get("name", "")
            if name and name not in seen_historical:
                seen_historical.add(name)
                merged["historical_founders"].append(f)

        # Also accept plain "founders" list (from older scrapers / LinkedIn)
        for f in data.get("founders", []):
            name = f.get("name", "")
            if name and name not in seen_historical:
                seen_historical.add(name)
                merged["historical_founders"].append({**f, "role": f.get("role", "Founder")})

        # Services / specialties (from LinkedIn)
        for svc in data.get("services", []):
            if svc and svc not in merged["services"]:
                merged["services"].append(svc)

        # Current leadership (Wikidata P169 CEO)
        for c in data.get("current_leadership", []):
            name = c.get("name", "")
            if name and name not in seen_leadership:
                seen_leadership.add(name)
                merged["current_leadership"].append(c)

        # Contact info — merge structured dict
        contact = data.get("contact", {})
        if isinstance(contact, dict):
            for k, v in contact.items():
                if k not in merged["contact"] and v:
                    merged["contact"][k] = v

        # Snippets — deduplicate
        for snippet in data.get("raw_snippets", []):
            if snippet not in merged["raw_snippets"]:
                merged["raw_snippets"].append(snippet)
        for snippet in data.get("financial_snippets", []):
            if snippet not in merged["financial_snippets"]:
                merged["financial_snippets"].append(snippet)
        for snippet in data.get("contact_snippets", []):
            if snippet not in merged["contact_snippets"]:
                merged["contact_snippets"].append(snippet)

    return merged


# ---------------------------------------------------------------------------
# Entrypoint — only used when running the MCP server standalone
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run()
