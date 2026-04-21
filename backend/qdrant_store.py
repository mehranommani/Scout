"""
Qdrant vector store helpers.

SDK: qdrant-client (async)
Docs: https://python-client.qdrant.tech/

Embeddings: nomic-embed-text via Ollama REST API
Ollama embed endpoint: POST /api/embeddings
"""
import asyncio
import logging
import uuid

import httpx
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct

from config import settings

logger = logging.getLogger(__name__)

_client: AsyncQdrantClient | None = None


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)
    return _client


async def init_collection() -> None:
    """Create the Qdrant collection if it does not exist."""
    client = get_client()
    collections = await client.get_collections()
    names = [c.name for c in collections.collections]
    if settings.QDRANT_COLLECTION not in names:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=settings.QDRANT_VECTOR_SIZE,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Qdrant collection '%s' created.", settings.QDRANT_COLLECTION)


async def _embed(text: str) -> list[float]:
    """Call Ollama /api/embed to get a vector for the text.
    Ollama ≥ 0.1.26 replaced /api/embeddings (deprecated) with /api/embed.
    Response shape: {"embeddings": [[float, ...]], ...}
    """
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/embed",
            json={"model": settings.EMBEDDING_MODEL, "input": text},
        )
        resp.raise_for_status()
        data = resp.json()
        # /api/embed returns a list of embeddings; take the first
        return data["embeddings"][0]


async def upsert_report(report_id: str, report_text: str, company_data: dict) -> str:
    """
    Embed the report text and upsert it to Qdrant.
    Returns the Qdrant point ID (same as report_id).
    """
    try:
        vector = await _embed(report_text[:4096])  # truncate to safe embed length
        point_id = str(uuid.UUID(report_id))       # ensure valid UUID format

        payload = {
            "report_id": report_id,
            "company_name": company_data.get("company_name", ""),
            "industry": company_data.get("industry"),
            "website": company_data.get("website"),
            "report_preview": report_text[:500],
        }

        client = get_client()
        await client.upsert(
            collection_name=settings.QDRANT_COLLECTION,
            points=[PointStruct(id=point_id, vector=vector, payload=payload)],
        )
        logger.info("Upserted report %s to Qdrant.", report_id)
        return point_id
    except Exception as e:
        logger.error("Qdrant upsert failed for report %s: %s", report_id, e)
        return ""


async def search_similar(query: str, limit: int = 5) -> list[dict]:
    """Search for reports similar to a query string."""
    try:
        vector = await _embed(query)
        client = get_client()
        response = await client.query_points(
            collection_name=settings.QDRANT_COLLECTION,
            query=vector,
            limit=limit,
            with_payload=True,
        )
        return [{"score": r.score, **(r.payload or {})} for r in response.points]
    except Exception as e:
        logger.error("Qdrant search failed: %s", e)
        return []
