"""
Scout FastAPI backend.

Endpoints:
  POST /api/research          — start a research session
  GET  /api/research/{id}/stream — SSE progress stream
  GET  /api/reports/{id}      — fetch a completed report
  GET  /api/reports           — list all reports
  GET  /api/health            — service health check
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

import db
import qdrant_store
from agent.graph import compiled_graph
from config import settings
from langfuse_client import get_langfuse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Per-session event queues for SSE
_queues: dict[str, asyncio.Queue] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await db.init_db()
    await qdrant_store.init_collection()
    logger.info("Scout backend started.")
    yield
    await db.close_db()
    logger.info("Scout backend stopped.")


app = FastAPI(title="Scout", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ResearchRequest(BaseModel):
    name: str


# ---------------------------------------------------------------------------
# SSE event emitter factory
# ---------------------------------------------------------------------------

def make_emitter(session_id: str):
    queue = _queues.get(session_id)

    def emit(stage: str, message: str, **extra):
        if queue is None:
            return
        payload = {"stage": stage, "message": message, **extra}
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            pass

    return emit


# ---------------------------------------------------------------------------
# POST /api/research
# ---------------------------------------------------------------------------

@app.post("/api/research", status_code=202)
async def start_research(body: ResearchRequest):
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Company name must not be empty.")

    session_id = await db.create_session(name)

    # Create SSE queue for this session
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _queues[session_id] = queue

    # Run agent in background
    asyncio.create_task(_run_agent(session_id, name, queue))

    return {
        "session_id": session_id,
        "status": "pending",
        "stream_url": f"/api/research/{session_id}/stream",
    }


async def _run_agent(session_id: str, name: str, queue: asyncio.Queue):
    """Background task: run the LangGraph agent and push events to the queue."""
    emitter = make_emitter(session_id)

    try:
        await db.update_session(session_id, status="running")

        lf = get_langfuse()
        trace_id = ""

        with lf.start_as_current_observation(
            name="company-research",
            as_type="span",
        ):
            # Capture the trace ID Langfuse assigned to this observation
            try:
                trace_id = lf.get_current_trace_id() or ""
                if trace_id:
                    await db.update_session(session_id, langfuse_trace_id=trace_id)
            except Exception:
                pass

            final_state = await compiled_graph.ainvoke({
                "session_id": session_id,
                "raw_input": name,
                "scrape_results": [],
                "attempt_number": 0,
                "validation_feedback": "",
                "langfuse_trace_id": trace_id,
                "emit": emitter,
            })

            # Populate trace input/output so Langfuse LLM-as-judge evaluators
            # can access the report via the {{output}} template variable.
            if isinstance(final_state, dict):
                report_text = final_state.get("report_text", "") or ""
                if report_text:
                    try:
                        # Call via getattr to avoid IDE strikethrough on the deprecated symbol.
                        # This method is intentionally kept in the SDK for trace-level
                        # LLM-as-judge evaluators (target_object="trace"), which is our setup.
                        getattr(lf, "set_current_trace_io")(input=name, output=report_text)
                    except Exception:
                        pass

        # Write completion metadata back to the session row
        now = datetime.now(timezone.utc)
        attempt = final_state.get("attempt_number", 0) if isinstance(final_state, dict) else 0
        await db.update_session(
            session_id,
            status="complete",
            completed_at=now,
            retry_count=attempt,
        )

        # Post validation_passed as a top-level trace score.
        # Structural dimension scores are posted by validate_report().
        # LLM-quality scores are added async by Langfuse's evaluator pipeline.
        if trace_id and isinstance(final_state, dict):
            passed = final_state.get("validation_passed")
            try:
                if passed is not None:
                    lf.create_score(
                        name="validation_passed",
                        value=1.0 if passed else 0.0,
                        trace_id=trace_id,
                    )
            except Exception as score_err:
                logger.warning("Langfuse validation_passed score failed: %s", score_err)

        try:
            lf.flush()
        except Exception:
            pass

    except Exception as e:
        logger.error("Agent error for session %s: %s", session_id, e)
        emitter(stage="error", message=f"Internal error: {e}")
        await db.update_session(session_id, status="failed", error_message=str(e))
    finally:
        # Sentinel to close the SSE stream
        await queue.put(None)


# ---------------------------------------------------------------------------
# GET /api/research/{session_id}/stream  — SSE
# ---------------------------------------------------------------------------

@app.get("/api/research/{session_id}/stream")
async def stream_research(session_id: str):
    session = await db.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    queue = _queues.get(session_id)
    if queue is None:
        # Session already completed — return a synthetic complete event
        async def already_done():
            yield {"event": "complete", "data": json.dumps({"message": "Already complete."})}
        return EventSourceResponse(already_done())

    async def event_generator():
        try:
            while True:
                item = await asyncio.wait_for(queue.get(), timeout=120)
                if item is None:
                    break
                stage = item.get("stage", "progress")
                event_type = "complete" if stage == "complete" else "error" if stage == "error" else "progress"
                yield {"event": event_type, "data": json.dumps(item)}
                if event_type in ("complete", "error"):
                    break
        except asyncio.TimeoutError:
            yield {"event": "error", "data": json.dumps({"message": "Stream timed out."})}
        finally:
            _queues.pop(session_id, None)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}
# ---------------------------------------------------------------------------

@app.get("/api/reports/{report_id}")
async def get_report(report_id: str):
    report = await db.get_report(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found.")
    # Deserialise JSONB fields
    for field in ("founders", "funding_rounds", "services", "contact", "sources_used"):
        if isinstance(report.get(field), str):
            try:
                report[field] = json.loads(report[field])
            except Exception:
                pass
    return report


# ---------------------------------------------------------------------------
# GET /api/reports
# ---------------------------------------------------------------------------

@app.get("/api/reports")
async def list_reports(limit: int | None = None, offset: int = 0):
    reports = await db.list_reports(limit=limit, offset=offset)
    return {"reports": reports, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# GET /api/health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health():
    checks = {"status": "ok", "db": False, "qdrant": False, "ollama": False}

    # DB
    try:
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        checks["db"] = True
    except Exception:
        pass

    # Qdrant
    try:
        client = qdrant_store.get_client()
        await client.get_collections()
        checks["qdrant"] = True
    except Exception:
        pass

    # Ollama
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            checks["ollama"] = resp.status_code == 200
    except Exception:
        pass

    if not all([checks["db"], checks["qdrant"], checks["ollama"]]):
        checks["status"] = "degraded"

    return checks


# ---------------------------------------------------------------------------
# GET /api/config
# ---------------------------------------------------------------------------

@app.get("/api/config")
async def get_config():
    from config import DATA_SOURCES
    return {
        "llm_model": settings.LLM_MODEL,
        "llm_base_url": settings.OLLAMA_BASE_URL,
        "validation": {
            "min_text_length": settings.VALIDATION_MIN_TEXT_LENGTH,
            "min_relevancy_score": settings.VALIDATION_MIN_RELEVANCY,
            "max_retries": settings.VALIDATION_MAX_RETRIES,
        },
        "search": {
            "max_results_per_query": 3,
            "num_queries": 3,
        },
        "sources": {
            k: {"enabled": v["enabled"], "use_api": v.get("use_api", False), "use_scrapling": v.get("use_scrapling", False)}
            for k, v in DATA_SOURCES.items()
        },
    }


# ---------------------------------------------------------------------------
# GET /api/stats  — aggregate metrics for the home page + eval console
# ---------------------------------------------------------------------------

@app.get("/api/stats")
async def get_stats():
    return await db.get_stats()


# ---------------------------------------------------------------------------
# GET /api/eval   — per-report evaluation rows
# ---------------------------------------------------------------------------

@app.get("/api/eval")
async def get_eval(limit: int = 100):
    rows = await db.list_eval(limit=limit)
    return {"rows": rows}
