"""
AgentState — the shared state that flows through all LangGraph nodes.
Uses TypedDict so LangGraph can merge partial updates from each node.

Split into a required base + optional extension so type-checkers know
which keys are always present and which may be absent.
"""
from typing import Annotated
import operator
from typing_extensions import TypedDict, Required


class AgentState(TypedDict, total=False):
    # ---- Always-required inputs (injected by FastAPI before graph starts) ----
    session_id: Required[str]
    raw_input: Required[str]

    # ---- Classification ----
    input_type: str             # "company" | "product" | "invalid"
    company_name: str           # canonical name (may differ from raw_input for products)
    error_message: str

    # ---- Scraping ----
    # Annotated with operator.add so each node can append without overwriting
    scrape_results: Annotated[list[dict], operator.add]

    # ---- Aggregation ----
    company_data: dict       # merged, normalised company information

    # ---- Report generation ----
    report_text: str
    attempt_number: int
    validation_feedback: str  # injected on retry

    # ---- Validation ----
    validation_passed: bool
    relevancy_score: float
    token_count_in: int
    token_count_out: int

    # ---- Storage ----
    report_id: str
    qdrant_point_id: str

    # ---- Product resolution ----
    product_name: str      # original product query when input_type == "product"
    parent_company: str    # web-verified owner/creator of the product

    # ---- Observability ----
    langfuse_trace_id: str

    # ---- SSE progress emitter (injected by FastAPI, not serialised) ----
    emit: object             # callable: emit(stage, message)
