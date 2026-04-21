"""
PostgreSQL access via raw asyncpg — no SQLAlchemy.
Tables are created on startup with CREATE TABLE IF NOT EXISTS.
"""
import asyncpg
import logging
from contextlib import asynccontextmanager

from config import settings

logger = logging.getLogger(__name__)

_pool: asyncpg.Pool | None = None

CREATE_TABLES_SQL = """
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS research_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    input_name TEXT NOT NULL,
    input_type TEXT CHECK(input_type IN ('company', 'product', 'invalid')),
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    retry_count SMALLINT DEFAULT 0,
    langfuse_trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS company_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID REFERENCES research_sessions(id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,
    industry TEXT,
    website TEXT,
    founded_date TEXT,
    founders JSONB DEFAULT '[]',
    funding_rounds JSONB DEFAULT '[]',
    services JSONB DEFAULT '[]',
    contact JSONB DEFAULT '{}',
    revenue_usd BIGINT,
    total_funding_usd BIGINT,
    report_text TEXT,
    sources_used JSONB DEFAULT '[]',
    validation_passed BOOLEAN,
    relevancy_score FLOAT,
    token_count_in INTEGER,
    token_count_out INTEGER,
    qdrant_point_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


async def init_db() -> None:
    global _pool
    _pool = await asyncpg.create_pool(
        settings.DATABASE_URL,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        await conn.execute(CREATE_TABLES_SQL)
    logger.info("Database pool initialised and schema ready.")


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call init_db() first.")
    return _pool


@asynccontextmanager
async def acquire():
    async with get_pool().acquire() as conn:
        yield conn


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

async def create_session(input_name: str) -> str:
    async with acquire() as conn:
        row = await conn.fetchrow(
            "INSERT INTO research_sessions (input_name) VALUES ($1) RETURNING id",
            input_name,
        )
        return str(row["id"])


async def update_session(session_id: str, **kwargs) -> None:
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    values = list(kwargs.values())
    sql = f"UPDATE research_sessions SET {fields} WHERE id = $1"
    async with acquire() as conn:
        await conn.execute(sql, session_id, *values)


async def get_session(session_id: str) -> dict | None:
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM research_sessions WHERE id = $1", session_id
        )
        return dict(row) if row else None


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

async def create_report(session_id: str, data: dict) -> str:
    import json
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO company_reports (
                session_id, company_name, industry, website, founded_date,
                founders, funding_rounds, services, contact,
                revenue_usd, total_funding_usd, report_text, sources_used,
                validation_passed, relevancy_score,
                token_count_in, token_count_out, qdrant_point_id
            ) VALUES (
                $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18
            ) RETURNING id
            """,
            session_id,
            data.get("company_name", ""),
            data.get("industry"),
            data.get("website"),
            data.get("founded_date"),
            json.dumps(data.get("founders", [])),
            json.dumps(data.get("funding_rounds", [])),
            json.dumps(data.get("services", [])),
            json.dumps(data.get("contact", {})),
            data.get("revenue_usd"),
            data.get("total_funding_usd"),
            data.get("report_text"),
            json.dumps(data.get("sources_used", [])),
            data.get("validation_passed"),
            data.get("relevancy_score"),
            data.get("token_count_in"),
            data.get("token_count_out"),
            data.get("qdrant_point_id"),
        )
        return str(row["id"])


async def update_report(report_id: str, **kwargs) -> None:
    """Patch individual columns on a company_reports row."""
    if not kwargs:
        return
    fields = ", ".join(f"{k} = ${i+2}" for i, k in enumerate(kwargs))
    values = list(kwargs.values())
    sql = f"UPDATE company_reports SET {fields} WHERE id = $1"
    async with acquire() as conn:
        await conn.execute(sql, report_id, *values)


async def get_report(report_id: str) -> dict | None:
    async with acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM company_reports WHERE id = $1", report_id
        )
        return dict(row) if row else None


async def list_reports(limit: int | None = None, offset: int = 0) -> list[dict]:
    from config import settings as _settings
    _limit = limit if limit is not None else _settings.REPORTS_PAGE_LIMIT
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, company_name, industry, founded_date,
                   validation_passed, relevancy_score, created_at
            FROM company_reports
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
            """,
            _limit, offset,
        )
        return [dict(r) for r in rows]


async def get_stats() -> dict:
    """Aggregate metrics across all reports and sessions."""
    async with acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT
                COUNT(*)                                                      AS total_reports,
                COUNT(*) FILTER (WHERE validation_passed = true)              AS passed_reports,
                ROUND(AVG(relevancy_score)::numeric, 3)                       AS avg_relevancy,
                SUM(token_count_in)                                           AS total_tokens_in,
                SUM(token_count_out)                                          AS total_tokens_out,
                ROUND(
                    AVG(
                        EXTRACT(EPOCH FROM (s.completed_at - s.created_at))
                    )::numeric, 1
                )                                                             AS avg_duration_sec
            FROM company_reports r
            LEFT JOIN research_sessions s ON s.id = r.session_id
            """
        )
        return dict(row) if row else {}


async def list_eval(limit: int | None = None) -> list[dict]:
    """Full evaluation data: one row per report with session metrics."""
    from config import settings as _settings
    _limit = limit if limit is not None else _settings.EVAL_ROWS_LIMIT
    async with acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                r.id,
                r.company_name,
                r.industry,
                r.website,
                r.sources_used,
                r.validation_passed,
                r.relevancy_score,
                r.token_count_in,
                r.token_count_out,
                r.created_at,
                s.retry_count,
                s.status        AS session_status,
                ROUND(
                    EXTRACT(EPOCH FROM (s.completed_at - s.created_at))::numeric, 1
                )               AS duration_sec
            FROM company_reports r
            LEFT JOIN research_sessions s ON s.id = r.session_id
            ORDER BY r.created_at DESC
            LIMIT $1
            """,
            _limit,
        )
        return [dict(r) for r in rows]
