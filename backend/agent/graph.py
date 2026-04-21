"""
LangGraph StateGraph assembly.
Compiled once at import time; re-used for all requests.

Graph flow:
  START → classify_input
            ↓ invalid  → emit_error → END
            ↓ product  → resolve_product → scrape_and_generate
            ↓ company  ──────────────────→ scrape_and_generate
                                                  ↓
                                          validate_and_store
                                             ↓ passed     → END
                                             ↓ retry(≤3)  → scrape_and_generate
                                             ↓ max_retries → END
"""
from typing import Literal
from langgraph.graph import StateGraph, START, END
from langgraph.graph.state import CompiledStateGraph

from agent.state import AgentState
from agent.nodes import (
    classify_input,
    resolve_product,
    scrape_and_generate,
    validate_and_store,
    emit_error,
)


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def route_after_classify(state: AgentState) -> Literal["resolve_product", "scrape_and_generate", "emit_error"]:
    t = state.get("input_type", "invalid")
    if t == "invalid":
        return "emit_error"
    if t == "product":
        return "resolve_product"
    return "scrape_and_generate"


def route_after_validate(state: AgentState) -> str:
    if state.get("validation_passed"):
        return END
    from config import settings
    if state.get("attempt_number", 1) >= settings.VALIDATION_MAX_RETRIES:
        return END  # max retries reached — best attempt already stored
    return "scrape_and_generate"


# ---------------------------------------------------------------------------
# Build and compile the graph
# ---------------------------------------------------------------------------

def build_graph() -> CompiledStateGraph:
    graph = StateGraph(AgentState)

    graph.add_node("classify_input", classify_input)
    graph.add_node("resolve_product", resolve_product)
    graph.add_node("scrape_and_generate", scrape_and_generate)
    graph.add_node("validate_and_store", validate_and_store)
    graph.add_node("emit_error", emit_error)

    graph.add_edge(START, "classify_input")

    graph.add_conditional_edges(
        "classify_input",
        route_after_classify,
        {
            "resolve_product": "resolve_product",
            "scrape_and_generate": "scrape_and_generate",
            "emit_error": "emit_error",
        },
    )

    graph.add_edge("resolve_product", "scrape_and_generate")
    graph.add_edge("scrape_and_generate", "validate_and_store")

    graph.add_conditional_edges(
        "validate_and_store",
        route_after_validate,
        {
            "scrape_and_generate": "scrape_and_generate",
            END: END,
        },
    )

    graph.add_edge("emit_error", END)

    return graph.compile()


# Singleton — compiled once
compiled_graph = build_graph()
