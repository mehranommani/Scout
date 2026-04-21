"""
Unit tests for individual scrapers.
Tests are designed to work offline by mocking httpx responses.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# OpenCorporates scraper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_opencorporates_success():
    from mcp_tools.scrapers.opencorporates import scrape

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "results": {
            "companies": [
                {
                    "company": {
                        "name": "Stripe, Inc.",
                        "jurisdiction_code": "us_de",
                        "company_number": "5277016",
                        "incorporation_date": "2010-09-22",
                        "opencorporates_url": "https://opencorporates.com/companies/us_de/5277016",
                        "industry_codes": [{"description": "Financial Technology"}],
                    }
                }
            ]
        }
    }

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = await scrape("Stripe")

    assert result["status"] == "success"
    assert result["data"]["company_name"] == "Stripe, Inc."
    assert result["data"]["jurisdiction"] == "us_de"
    assert result["source"] == "opencorporates"


@pytest.mark.asyncio
async def test_opencorporates_no_data():
    from mcp_tools.scrapers.opencorporates import scrape

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"results": {"companies": []}}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = await scrape("XYZ_NONEXISTENT_CORP")

    assert result["status"] == "no_data"
    assert result["data"] is None


@pytest.mark.asyncio
async def test_opencorporates_http_error():
    import httpx
    from mcp_tools.scrapers.opencorporates import scrape

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        mock_client.get.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=MagicMock(status_code=429),
        )

        result = await scrape("Stripe")

    assert result["status"] == "failed"
    assert result["data"] is None


# ---------------------------------------------------------------------------
# Wikidata scraper
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_wikidata_success():
    from mcp_tools.scrapers.wikidata import scrape

    core_response = MagicMock()
    core_response.raise_for_status = MagicMock()
    core_response.json.return_value = {
        "results": {
            "bindings": [
                {
                    "company": {"value": "http://www.wikidata.org/entity/Q7235382"},
                    "companyLabel": {"value": "Stripe"},
                    "description": {"value": "American financial services company"},
                    "inception": {"value": "2010-09-22T00:00:00Z"},
                    "website": {"value": "https://stripe.com"},
                    "industryLabel": {"value": "Financial technology"},
                    "founderLabel": {"value": "Patrick Collison"},
                }
            ]
        }
    }

    contact_response = MagicMock()
    contact_response.raise_for_status = MagicMock()
    contact_response.json.return_value = {"results": {"bindings": []}}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        # Wikidata scraper uses client.post for SPARQL queries.
        # First call = core query, second call = contact query.
        mock_client.post = AsyncMock(side_effect=[core_response, contact_response])

        result = await scrape("Stripe")

    assert result["status"] == "success"
    assert result["data"]["company_name"] == "Stripe"
    assert result["data"]["website"] == "https://stripe.com"
    assert any(f["name"] == "Patrick Collison" for f in result["data"]["historical_founders"])


@pytest.mark.asyncio
async def test_wikidata_empty_results():
    from mcp_tools.scrapers.wikidata import scrape

    empty_response = MagicMock()
    empty_response.raise_for_status = MagicMock()
    empty_response.json.return_value = {"results": {"bindings": []}}

    with patch("httpx.AsyncClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client
        # Wikidata scraper uses client.post for SPARQL queries.
        mock_client.post = AsyncMock(return_value=empty_response)

        result = await scrape("DOESNOTEXIST_LLC")

    assert result["status"] == "no_data"


# ---------------------------------------------------------------------------
# Crunchbase scraper — skipped when API key is blank
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_crunchbase_skipped_without_key():
    from mcp_tools.scrapers.crunchbase import scrape

    with patch("mcp_tools.scrapers.crunchbase.settings") as mock_settings:
        mock_settings.CRUNCHBASE_API_KEY = ""
        result = await scrape("Stripe")

    assert result["status"] == "skipped"


# ---------------------------------------------------------------------------
# MCP tools: validate_name_format
# ---------------------------------------------------------------------------

def test_validate_name_format_valid_company():
    from mcp_tools.server import validate_name_format
    result = validate_name_format("Stripe Inc")
    assert result["likely_valid"] is True


def test_validate_name_format_too_short():
    from mcp_tools.server import validate_name_format
    result = validate_name_format("A")
    assert result["likely_valid"] is False


def test_validate_name_format_too_long():
    from mcp_tools.server import validate_name_format
    result = validate_name_format("A" * 301)
    assert result["likely_valid"] is False


def test_validate_name_format_personal_name_with_suffix():
    from mcp_tools.server import validate_name_format
    result = validate_name_format("John Smith Jr")
    assert result["likely_valid"] is False


# ---------------------------------------------------------------------------
# MCP tools: merge_source_results
# ---------------------------------------------------------------------------

def test_merge_source_results_basic():
    from mcp_tools.server import merge_source_results

    results = [
        {
            "source": "wikidata",
            "status": "success",
            "data": {
                "company_name": "Stripe",
                "description": "A fintech company",
                "website": "https://stripe.com",
                "founders": [{"name": "Patrick Collison", "role": "Founder"}],
                "industry": "Fintech",
                "founded_date": "2010-09-22",
                "jurisdiction": None,
                "revenue_usd": None,
                "total_funding_usd": None,
                "employee_count": None,
                "linkedin_url": None,
                "contact": {},
                "raw_snippets": [],
            },
        },
        {
            "source": "opencorporates",
            "status": "success",
            "data": {
                "company_name": "Stripe, Inc.",
                "description": None,
                "website": None,
                "founders": [],
                "industry": "Financial Technology",
                "founded_date": None,
                "jurisdiction": "us_de",
                "revenue_usd": None,
                "total_funding_usd": None,
                "employee_count": None,
                "linkedin_url": None,
                "contact": {"address": "123 Main St"},
                "raw_snippets": [],
            },
        },
    ]

    merged = merge_source_results(results, "Stripe")
    assert merged["website"] == "https://stripe.com"
    assert merged["industry"] == "Fintech"          # wikidata wins (first)
    assert merged["jurisdiction"] == "us_de"        # opencorporates fills it in
    assert merged["contact"]["address"] == "123 Main St"
    assert len(merged["historical_founders"]) == 1    # deduplicated
    assert "wikidata" in merged["sources_used"]
    assert "opencorporates" in merged["sources_used"]


def test_merge_skips_failed_sources():
    from mcp_tools.server import merge_source_results

    results = [
        {"source": "linkedin", "status": "failed", "data": None},
        {
            "source": "wikidata",
            "status": "success",
            "data": {
                "company_name": "OpenAI",
                "website": "https://openai.com",
                "founders": [],
                "industry": "AI Research",
                "description": None,
                "founded_date": None,
                "jurisdiction": None,
                "revenue_usd": None,
                "total_funding_usd": None,
                "employee_count": None,
                "linkedin_url": None,
                "contact": {},
                "raw_snippets": [],
            },
        },
    ]

    merged = merge_source_results(results, "OpenAI")
    assert "linkedin" not in merged["sources_used"]
    assert "wikidata" in merged["sources_used"]
