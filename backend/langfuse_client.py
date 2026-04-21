"""
Langfuse observability — Langfuse SDK v3/v4.

Architecture
────────────
This module handles TWO layers of evaluation:

1. STRUCTURAL SCORES (synchronous, in-agent-loop)
   Posted via lf.create_score() during validate_report().
   These drive retry decisions and give the Langfuse dashboard
   pass/fail signals per dimension:
     structure/sections_complete   — all 6 required sections present
     structure/min_length          — above minimum character threshold
     structure/financials_grounded — Financials has real data, not placeholders
     structure/contact_grounded    — Contact has real data, not placeholders
     structure/overall             — weighted aggregate (drives retry logic)

2. QUALITY SCORES (asynchronous, via Langfuse built-in evaluator)
   LLM-as-judge evaluators are configured in the Langfuse UI:
     localhost:3001 → Settings → Evaluators
   They run automatically on every new trace using Ollama via the
   Langfuse LLM Connection (configured in Settings → LLM Connections).
   No Python code required — Langfuse handles scheduling, execution,
   and score posting.

Langfuse LLM Connection setup (one-time, in the UI):
  Provider : OpenAI  (Ollama is OpenAI-compatible)
  Base URL : http://host.docker.internal:11434/v1
  API Key  : ollama
  Model    : qwen2.5:14b
"""
import logging
import os

from langfuse import get_client

from config import settings

logger = logging.getLogger(__name__)

os.environ.setdefault("LANGFUSE_PUBLIC_KEY", settings.LANGFUSE_PUBLIC_KEY)
os.environ.setdefault("LANGFUSE_SECRET_KEY", settings.LANGFUSE_SECRET_KEY)
os.environ.setdefault("LANGFUSE_HOST", settings.LANGFUSE_HOST)


def get_langfuse():
    return get_client()


def make_trace_id() -> str:
    try:
        return get_langfuse().create_trace_id()
    except Exception as e:
        logger.warning("Langfuse trace ID generation failed: %s", e)
        return ""


# ── Section helpers ──────────────────────────────────────────────────────────

def _extract_section(report_text: str, heading: str) -> str:
    lower = report_text.lower()
    start = lower.find(heading.lower())
    if start == -1:
        return ""
    next_heading = lower.find("\n##", start + len(heading))
    return report_text[start: next_heading if next_heading != -1 else len(report_text)]


def _section_has_real_data(section_text: str) -> bool:
    if not section_text:
        return False
    placeholders = {"not available in data sources.", "not available.", "n/a", "none"}
    lines = [
        l.strip() for l in section_text.splitlines()
        if l.strip() and not l.strip().startswith("#")
    ]
    return any(l.lower().rstrip(".") not in placeholders for l in lines)


# ── Structural validation ────────────────────────────────────────────────────

_REQUIRED_SECTIONS = (
    "## Overview",
    "## Current Leadership",
    "## Historical Founders",
    "## Products & Services",
    "## Financials",
    "## Contact & Sources",
)

# Weights for structural score — must sum to 1.0
_STRUCTURAL_WEIGHTS = {
    "structure/sections_complete":   0.40,
    "structure/min_length":          0.20,
    "structure/financials_grounded": 0.20,
    "structure/contact_grounded":    0.20,
}


async def validate_report(
    report_text: str,
    company_name: str,
    trace_id: str = "",
) -> tuple[bool, float, str]:
    """
    Validate report quality via deterministic structural checks.

    Returns (passed, relevancy_score, feedback_for_retry).

    Structural scores are posted to Langfuse immediately so the dashboard
    reflects per-dimension quality for every run.

    LLM-as-judge quality evaluation (hallucination detection, factual
    grounding, coherence) is handled by Langfuse's built-in async evaluator
    pipeline — configure it once in the Langfuse UI, then it runs
    automatically on every new trace with no code changes required.
    """
    failures: list[str] = []
    dim_scores: dict[str, float] = {}

    # ── Check 1: all 6 required sections present ─────────────────────────────
    missing = [s for s in _REQUIRED_SECTIONS if s.lower() not in report_text.lower()]
    if missing:
        dim_scores["structure/sections_complete"] = 0.0
        failures.append(
            f"Missing required section(s): {', '.join(missing)}. "
            "Every section must appear even if the content is 'Not available in data sources.'"
        )
    else:
        dim_scores["structure/sections_complete"] = 1.0

    # ── Check 2: minimum text length ─────────────────────────────────────────
    if len(report_text) < settings.VALIDATION_MIN_TEXT_LENGTH:
        dim_scores["structure/min_length"] = 0.0
        failures.append(
            f"Report too short ({len(report_text)} chars, "
            f"minimum {settings.VALIDATION_MIN_TEXT_LENGTH}). Expand each section."
        )
    else:
        dim_scores["structure/min_length"] = 1.0

    # ── Check 3: Financials section has real data ─────────────────────────────
    financials_text = _extract_section(report_text, "## Financials")
    if financials_text and not _section_has_real_data(financials_text):
        dim_scores["structure/financials_grounded"] = 0.0
        failures.append(
            "Financials section contains only placeholder text. "
            "Include at least one real figure from the financial snippets, "
            "or state explicitly that the company does not disclose financial data."
        )
    else:
        dim_scores["structure/financials_grounded"] = 1.0

    # ── Check 4: Contact section has real data ────────────────────────────────
    contact_text = _extract_section(report_text, "## Contact & Sources")
    if contact_text and not _section_has_real_data(contact_text):
        dim_scores["structure/contact_grounded"] = 0.0
        failures.append(
            "Contact section contains only placeholder text. "
            "Include website URL, email, phone, or address from the structured contact data."
        )
    else:
        dim_scores["structure/contact_grounded"] = 1.0

    # ── Aggregate structural score ────────────────────────────────────────────
    relevancy = round(
        sum(dim_scores[k] * _STRUCTURAL_WEIGHTS[k] for k in dim_scores),
        3,
    )

    # Log the breakdown to backend stdout for immediate visibility
    lines = [
        f"  {'✓' if v == 1.0 else '✗'} {k:<36} {'pass' if v == 1.0 else 'FAIL'}"
        for k, v in dim_scores.items()
    ]
    logger.info(
        "Structural validation for '%s':\n%s\n  → structure/overall = %.2f",
        company_name, "\n".join(lines), relevancy,
    )

    # ── Post all dimension scores to Langfuse ────────────────────────────────
    # These appear immediately in the Langfuse trace scores panel.
    # LLM-quality scores (hallucination, coherence, etc.) are added
    # asynchronously by Langfuse's built-in evaluator pipeline.
    if trace_id:
        try:
            lf = get_langfuse()
            for name, value in dim_scores.items():
                lf.create_score(
                    name=name,
                    value=value,
                    trace_id=trace_id,
                    data_type="BOOLEAN",   # 1.0 = pass, 0.0 = fail
                )
            lf.create_score(
                name="structure/overall",
                value=relevancy,
                trace_id=trace_id,
                data_type="NUMERIC",
                comment=(
                    "Weighted structural score. "
                    "LLM-quality scores added async by Langfuse evaluator."
                ),
            )
        except Exception as e:
            logger.warning("Langfuse score posting failed: %s", e)

    # ── Log validation span to Langfuse ─────────────────────────────────────
    try:
        lf = get_langfuse()
        with lf.start_as_current_observation(
            name="report-validation",
            as_type="span",
            output={
                "passed": len(failures) == 0,
                "structure_score": relevancy,
                "dimension_scores": dim_scores,
                "failures": failures,
                "text_length": len(report_text),
                "note": (
                    "LLM-quality evaluation (hallucination, factual grounding) "
                    "runs async via Langfuse evaluator pipeline."
                ),
            },
        ):
            pass
    except Exception as e:
        logger.warning("Langfuse validation span failed: %s", e)

    passed = len(failures) == 0
    feedback = ""
    if failures:
        feedback = (
            "The previous report had these structural issues:\n"
            + "\n".join(f"- {f}" for f in failures)
            + "\nFix ALL of these in the new report."
        )

    return passed, relevancy, feedback
