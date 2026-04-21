"""
Integration tests for the FastAPI endpoints.
Uses httpx.AsyncClient with the ASGI transport — no real DB or agent needed.
"""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app():
    """Import app after patching heavy startup dependencies."""
    import main
    return main.app


# ---------------------------------------------------------------------------
# POST /api/research
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_research_returns_session_id():
    """Valid name → 202 with session_id and stream_url."""
    fake_session_id = "aaaaaaaa-0000-0000-0000-000000000001"

    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()), \
         patch("db.create_session", new=AsyncMock(return_value=fake_session_id)), \
         patch("asyncio.create_task"):  # don't actually run the agent

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/research", json={"name": "Stripe"})

    assert resp.status_code == 202
    body = resp.json()
    assert body["session_id"] == fake_session_id
    assert "stream_url" in body
    assert fake_session_id in body["stream_url"]


@pytest.mark.asyncio
async def test_post_research_empty_name_returns_422():
    """Empty name → 422 validation error."""
    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()):

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/research", json={"name": "   "})

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_report_returns_data():
    """Known report_id → 200 with report fields."""
    fake_report = {
        "id": "rrrrrrrr-0000-0000-0000-000000000001",
        "session_id": "ssssssss-0000-0000-0000-000000000001",
        "company_name": "Stripe",
        "industry": "Fintech",
        "website": "https://stripe.com",
        "founded_date": "2010",
        "founders": json.dumps([{"name": "Patrick Collison", "role": "Founder"}]),
        "funding_rounds": json.dumps([]),
        "services": json.dumps([]),
        "contact": json.dumps({}),
        "revenue_usd": None,
        "total_funding_usd": None,
        "report_text": "## Overview\nStripe is a payment company.\n## Founders\nPatrick.",
        "sources_used": json.dumps(["wikidata"]),
        "validation_passed": True,
        "relevancy_score": 0.9,
        "token_count_in": 100,
        "token_count_out": 200,
        "created_at": "2026-04-16T00:00:00Z",
        "qdrant_point_id": None,
    }

    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()), \
         patch("db.get_report", new=AsyncMock(return_value=fake_report)):

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/reports/{fake_report['id']}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["company_name"] == "Stripe"
    assert isinstance(body["founders"], list)  # JSONB deserialised
    assert body["founders"][0]["name"] == "Patrick Collison"


@pytest.mark.asyncio
async def test_get_report_not_found():
    """Unknown report_id → 404."""
    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()), \
         patch("db.get_report", new=AsyncMock(return_value=None)):

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/reports/nonexistent-id")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/reports
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_reports():
    """List endpoint → 200 with reports array."""
    fake_rows = [
        {"id": "r1", "company_name": "Stripe", "industry": "Fintech", "created_at": "2026-04-16"},
        {"id": "r2", "company_name": "OpenAI", "industry": "AI", "created_at": "2026-04-15"},
    ]

    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()), \
         patch("db.list_reports", new=AsyncMock(return_value=fake_rows)):

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/reports")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["reports"]) == 2
    assert body["reports"][0]["company_name"] == "Stripe"


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health_all_ok():
    """All services up → status ok."""
    mock_pool = MagicMock()
    mock_conn = AsyncMock()
    mock_conn.fetchval = AsyncMock(return_value=1)
    mock_pool.acquire.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.acquire.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_qdrant = AsyncMock()
    mock_qdrant.get_collections = AsyncMock(return_value=MagicMock())

    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()), \
         patch("db.get_pool", return_value=mock_pool), \
         patch("qdrant_store.get_client", return_value=mock_qdrant), \
         patch("httpx.AsyncClient") as mock_http:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_http.return_value)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value.get = AsyncMock(return_value=mock_resp)

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["db"] is True
    assert body["qdrant"] is True
    assert body["ollama"] is True


@pytest.mark.asyncio
async def test_health_degraded_when_db_down():
    """DB unavailable → status degraded."""
    with patch("db.init_db", new=AsyncMock()), \
         patch("db.close_db", new=AsyncMock()), \
         patch("qdrant_store.init_collection", new=AsyncMock()), \
         patch("db.get_pool", side_effect=Exception("DB unreachable")), \
         patch("qdrant_store.get_client", side_effect=Exception("Qdrant down")), \
         patch("httpx.AsyncClient") as mock_http:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_http.return_value.__aenter__ = AsyncMock(return_value=mock_http.return_value)
        mock_http.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_http.return_value.get = AsyncMock(return_value=mock_resp)

        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["db"] is False
