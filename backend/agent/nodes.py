"""
All LangGraph node functions in one file (MVP simplicity).
Each node takes AgentState and returns a partial dict to merge back.
"""
import asyncio
import json
import logging
from typing import Any

from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage

from config import settings, DATA_SOURCES
from agent.state import AgentState
from mcp_tools.server import call_tool_data

logger = logging.getLogger(__name__)

# Shared LLM instance
llm = ChatOllama(model=settings.LLM_MODEL, temperature=settings.LLM_TEMPERATURE)


def _content_str(content: Any) -> str:
    """Extract a plain string from an AIMessage.content.

    langchain-core 1.x changed content to str | list[str | dict].
    This helper normalises both forms to a single string.
    """
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            parts.append(block.get("text", ""))
    return "".join(parts)


def _emit(state: AgentState, stage: str, message: str, **extra) -> None:
    """Fire SSE event if an emitter is wired in."""
    emitter = state.get("emit")
    if callable(emitter):
        emitter(stage=stage, message=message, **extra)


# ---------------------------------------------------------------------------
# Node 1: classify_input
# ---------------------------------------------------------------------------
def _ddg_snippets(name: str) -> list[str]:
    """
    Synchronous: fetch top-5 DuckDuckGo snippets for the name.
    Returns a list of 'Title — Body' strings, empty on failure.
    """
    from ddgs import DDGS
    try:
        with DDGS() as ddgs:
            hits = list(ddgs.text(f'"{name}"', max_results=5))
        return [
            f"{h.get('title', '').strip()} — {h.get('body', '').strip()}"
            for h in hits if h.get("body")
        ]
    except Exception as e:
        logger.warning("DDG classify-fallback search failed: %s", e)
        return []


async def classify_input(state: AgentState) -> dict:
    _emit(state, "classifying", f"Checking if '{state['raw_input']}' is a company, product, or invalid.")

    raw = state["raw_input"].strip()

    # Step 1: Quick heuristic pre-check — no LLM needed
    pre: dict[str, Any] = await call_tool_data("validate_name_format", {"name": raw}) or {}
    if not pre.get("likely_valid", True):
        return {
            "input_type": "invalid",
            "company_name": raw,
            "error_message": pre.get("reason", "Input rejected by format check."),
        }

    # Step 2: LLM classification from training knowledge.
    # IMPORTANT BIAS: prefer "company" over "product" for brand names.
    # Most tech names users search for (Figma, Notion, Linear, Vercel, Canva,
    # Stripe, Slack, Zoom, Shopify, etc.) are companies even though they also
    # make products. Classify as "product" ONLY when the name clearly refers to
    # a sub-product of a different parent company (e.g. iPhone → Apple,
    # Windows → Microsoft, ChatGPT → OpenAI, GitHub Copilot → GitHub/Microsoft).
    prompt = f"""Classify the following input as exactly one of: company, product, person, or unknown.

Strict definitions:
- "company"  : A brand, startup, business, or organisation that operates as its own entity.
               IMPORTANT: Most tech names (Figma, Notion, Linear, Vercel, Canva, Stripe,
               Slack, Zoom, Shopify, Kiro) are companies even if they are also products.
               When in doubt, prefer "company" over "product".
- "product"  : A sub-product of a DIFFERENT parent company where the name does NOT refer
               to the company itself. Examples: iPhone (Apple's product), Windows (Microsoft's),
               ChatGPT (OpenAI's product line), GitHub Copilot (GitHub/Microsoft). Do NOT
               classify something as "product" just because it is software or a SaaS app.
- "person"   : A personal name or individual's identifier.
- "unknown"  : You cannot determine the type from training knowledge alone.

Do NOT classify as "person" or "invalid" just because a name is unfamiliar.
Use "unknown" when unsure so a web check follows.

Input: "{raw}"

Respond with valid JSON only, no extra text:
{{"type": "<company|product|person|unknown>", "canonical_name": "<cleaned name>", "reason": "<one sentence>"}}"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    text = _content_str(response.content).strip()

    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    try:
        parsed = json.loads(text)
        input_type = parsed.get("type", "unknown").lower()
        canonical = parsed.get("canonical_name", raw)
        reason = parsed.get("reason", "")
    except json.JSONDecodeError:
        logger.warning("LLM classification JSON parse failed: %s", text)
        input_type = "unknown"
        canonical = raw
        reason = ""

    if input_type not in ("company", "product", "person", "unknown"):
        input_type = "unknown"

    # "person" from LLM is immediately invalid — no web check needed.
    if input_type == "person":
        return {
            "input_type": "invalid",
            "company_name": raw,
            "error_message": reason or f"'{raw}' appears to be a personal name.",
        }

    # Step 3: LLM confident about company/product — done.
    if input_type in ("company", "product"):
        return {"input_type": input_type, "company_name": canonical}

    # Step 4: LLM said "unknown" — do a web search and re-ask the LLM with evidence.
    _emit(state, "classifying", f"Checking web for '{raw}'…")
    snippets = _ddg_snippets(raw)

    if not snippets:
        # Nothing on the web either — truly unrecognisable
        return {
            "input_type": "invalid",
            "company_name": raw,
            "error_message": f"'{raw}' could not be identified as a company, product, or known entity.",
        }

    snippets_text = "\n".join(f"- {s}" for s in snippets[:5])
    web_prompt = f"""You searched the web for "{raw}" and found these results:

{snippets_text}

Based solely on these search results, classify "{raw}" as one of:
- "company"  : the search results describe a business, organisation, startup, or brand.
- "product"  : the search results describe a software, app, or specific product/service.
- "person"   : the search results are primarily about an individual person or their personal profiles.
- "invalid"  : the results are unrelated, ambiguous, or refer to something other than a company/product/person.

Respond with valid JSON only:
{{"type": "<company|product|person|invalid>", "canonical_name": "<best name from results>", "reason": "<one sentence>"}}"""

    web_response = await llm.ainvoke([HumanMessage(content=web_prompt)])
    web_text = _content_str(web_response.content).strip()
    if web_text.startswith("```"):
        web_text = web_text.split("```")[1]
        if web_text.startswith("json"):
            web_text = web_text[4:]
    web_text = web_text.strip()

    try:
        web_parsed = json.loads(web_text)
        web_type = web_parsed.get("type", "invalid").lower()
        web_canonical = web_parsed.get("canonical_name", raw)
        web_reason = web_parsed.get("reason", "")
    except json.JSONDecodeError:
        web_type = "invalid"
        web_canonical = raw
        web_reason = "Could not parse web-based classification."

    if web_type not in ("company", "product", "person", "invalid"):
        web_type = "invalid"

    if web_type in ("company", "product"):
        logger.info("Web-fallback classified '%s' as '%s'", raw, web_type)
        return {"input_type": web_type, "company_name": web_canonical}

    # person or invalid from web check → reject
    return {
        "input_type": "invalid",
        "company_name": raw,
        "error_message": web_reason or f"'{raw}' does not appear to be a company or product.",
    }


# ---------------------------------------------------------------------------
# Node 2: resolve_product  (only if input_type == "product")
# ---------------------------------------------------------------------------
async def resolve_product(state: AgentState) -> dict:
    """
    Discover the parent company for a product, grounded in live web search.

    Key design decisions:
    - Does NOT replace company_name. The product stays as the primary research subject.
    - Stores parent_company separately so the report can reference it without
      losing the user's original query (searching "Kiro" should produce a Kiro
      report that mentions AWS, not an AWS report).
    - Uses DuckDuckGo first; LLM only parses evidence, never recalls from memory.
      This eliminates hallucinated ownership (e.g. Figma → Autodesk).
    """
    product = state.get("company_name") or state["raw_input"]
    _emit(state, "resolving", f"Finding the company behind '{product}' using web search…")

    # Step 1: Web search — grounded evidence, not LLM memory.
    hits: list[str] = []
    try:
        from ddgs import DDGS
        loop = asyncio.get_event_loop()

        def _search() -> list[dict]:
            with DDGS() as ddgs:
                return list(ddgs.text(
                    f'"{product}" parent company OR "owned by" OR "made by" OR "created by"',
                    max_results=6,
                ))

        raw_hits = await loop.run_in_executor(None, _search)
        hits = [
            f"{h.get('title','').strip()} — {h.get('body','').strip()}"
            for h in raw_hits if h.get("body")
        ]
    except Exception as e:
        logger.warning("DDG ownership search failed for '%s': %s", product, e)

    if not hits:
        # No web evidence — treat as standalone entity, research the product directly.
        _emit(state, "resolving", f"No ownership data found. Researching '{product}' directly.")
        return {"product_name": product, "parent_company": ""}

    snippets_text = "\n".join(f"- {s}" for s in hits[:5])

    # Step 2: LLM extracts parent company from real web evidence only.
    # The LLM must base its answer solely on the snippets — no recall.
    prompt = f"""You are extracting ownership information about a product from web search results.
Do NOT use any knowledge from your training data. Base your answer ONLY on the snippets below.

Product: "{product}"

Web search snippets:
{snippets_text}

Task: Determine if "{product}" is a sub-product of a larger parent company.

Rules:
- If the snippets clearly state that "{product}" is made/owned/developed by a DIFFERENT company,
  return that company as parent_company and set is_standalone to false.
- If the snippets show "{product}" operates as its own company or the ownership is ambiguous,
  set is_standalone to true and return "{product}" as parent_company.
- If confidence is low, set is_standalone to true.

Respond with valid JSON only:
{{"parent_company": "<company name or '{product}' if standalone>", "is_standalone": <true|false>, "confidence": "<high|medium|low>", "evidence": "<exact quote from snippets supporting this>"}}"""

    response = await llm.ainvoke([HumanMessage(content=prompt)])
    text = _content_str(response.content).strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()

    parent_company = ""
    try:
        parsed = json.loads(text)
        is_standalone = parsed.get("is_standalone", True)
        confidence = parsed.get("confidence", "low")
        raw_parent = parsed.get("parent_company", product)
        evidence = parsed.get("evidence", "")

        if is_standalone or confidence == "low" or raw_parent.lower() == product.lower():
            parent_company = ""
            _emit(state, "resolving", f"'{product}' is a standalone entity. Researching it directly.")
        else:
            parent_company = raw_parent
            _emit(state, "resolving", f"'{product}' is a product of '{parent_company}' (evidence: {evidence[:80]}…)")
    except json.JSONDecodeError:
        logger.warning("resolve_product JSON parse failed: %s", text)
        _emit(state, "resolving", f"Could not parse ownership. Researching '{product}' directly.")

    # company_name stays as the product name — the product is the research subject.
    # parent_company is stored separately and referenced in the report.
    return {
        "product_name": product,
        "parent_company": parent_company,
    }


# ---------------------------------------------------------------------------
# Node 3: scrape_and_generate
# Scrapes all enabled sources, merges data, generates LLM report.
# ---------------------------------------------------------------------------
async def scrape_and_generate(state: AgentState) -> dict:
    company_name = state.get("company_name") or state["raw_input"]
    attempt = state.get("attempt_number", 0) + 1
    _emit(state, "scraping", f"Scraping sources for '{company_name}' (attempt {attempt}).")

    # Determine which sources to run (skip ones requiring missing API keys)
    enabled_sources: list[str] = []
    for name, cfg in DATA_SOURCES.items():
        if not cfg["enabled"]:
            continue
        if cfg.get("requires_key"):
            key_attr = f"{name.upper()}_API_KEY"
            if not getattr(settings, key_attr, ""):
                continue
        if name != "duckduckgo":  # DuckDuckGo is fallback only
            enabled_sources.append(name)

    # Fan-out: primary sources + DuckDuckGo always in parallel.
    # DDG always runs because it provides financial/contact snippets that
    # structured sources (Wikidata, LinkedIn) don't supply.
    all_sources = enabled_sources + ["duckduckgo"]

    async def _scrape(src: str) -> dict[str, Any]:
        """Wrap each scraper call with a hard timeout so one source can't block the pipeline."""
        logger.info("Starting scrape: %s", src)
        try:
            result = await asyncio.wait_for(
                call_tool_data("scrape_source", {"company_name": company_name, "source": src}),
                timeout=60.0,
            )
            logger.info("Finished scrape: %s → %s", src, result.get("status") if isinstance(result, dict) else "non-dict")
            return result if isinstance(result, dict) else {"source": src, "status": "failed", "data": None}
        except asyncio.TimeoutError:
            logger.warning("Scrape timeout for source: %s", src)
            return {"source": src, "status": "failed", "error": "timeout", "data": None}
        except Exception as e:
            logger.warning("Scrape error for source %s: %s", src, e)
            return {"source": src, "status": "failed", "error": str(e), "data": None}

    gather_results: list[Any] = list(await asyncio.gather(*[_scrape(s) for s in all_sources]))
    raw_results: list[dict[str, Any]] = [r for r in gather_results if isinstance(r, dict)]

    # Emit per-source status (skip duckduckgo — it's always supplementary)
    for r in raw_results:
        if r.get("source") != "duckduckgo":
            _emit(state, "source_result", f"{r['source']}: {r['status']}", source=r["source"], status=r["status"])

    # Merge all results
    merged: Any = await call_tool_data(
        "merge_source_results",
        {"results": raw_results, "company_name": company_name},
    )
    company_data: dict[str, Any] = merged if isinstance(merged, dict) else {"company_name": company_name}

    # Determine if this is a product-mode run
    product_name = state.get("product_name") or ""
    parent_company = state.get("parent_company") or ""
    is_product_mode = bool(product_name)

    _emit(state, "generating", f"Generating report for '{company_name}' (attempt {attempt}).")

    feedback = state.get("validation_feedback") or ""
    feedback_section = (
        f"\n\nPREVIOUS ATTEMPT ISSUES TO FIX:\n{feedback}\n"
        if feedback else ""
    )

    general_snippets   = "\n".join(company_data.get("raw_snippets", [])[:6])
    financial_snippets = "\n".join(company_data.get("financial_snippets", [])[:5])
    contact_snippets   = "\n".join(company_data.get("contact_snippets", [])[:4])

    historical_founders_text = json.dumps(company_data.get("historical_founders", []), indent=2)
    current_leadership_text  = json.dumps(company_data.get("current_leadership", []), indent=2)
    contact_struct           = json.dumps(company_data.get("contact", {}), indent=2)
    services_text = ", ".join(company_data.get("services", [])) or "Not available in data sources."

    system_prompt = """You are a business intelligence analyst producing a factual dossier.

STRICT RULES — violating any of these causes the report to fail validation:
1. ONLY use information from the structured data fields and web snippets provided below.
   Do NOT use your training-data knowledge to fill any gap.
2. If a field is missing from the data, write exactly: "Not available in data sources."
   Never guess, invent, or paraphrase training knowledge.
3. Historical founders are people who co-founded the entity.
   They may no longer be associated with it — note this explicitly.
   Current leadership comes from the "Current Leadership" field only.
4. Financial figures must be quoted verbatim from the snippets or structured fields.
   If no figure is present in the data, write "Not available in data sources."
5. Contact fields (email, phone, address) must come only from the structured contact
   dict or the [CONTACT] snippets. Do not invent contact details.
6. Every section must be present even if the answer is "Not available in data sources."
""" + (f"\n{feedback_section}" if feedback_section else "")

    # Parent company context block — only injected in product mode
    parent_block = ""
    if is_product_mode and parent_company:
        parent_block = f"\nParent/owner company (web-verified): {parent_company}\n"
    elif is_product_mode:
        parent_block = "\nParent/owner company: Not available in data sources.\n"

    user_prompt = f"""=== {'PRODUCT' if is_product_mode else 'COMPANY'} DATA (source-verified) ===
{'Product' if is_product_mode else 'Company'} name: {company_data.get('company_name', company_name)}
{parent_block}Company type:    {company_data.get('company_type') or 'Not available in data sources.'}
Description:     {company_data.get('description') or 'Not available in data sources.'}
Industry:        {company_data.get('industry') or 'Not available in data sources.'}
Founded:         {company_data.get('founded_date') or 'Not available in data sources.'}
Headquarters:    {company_data.get('headquarters') or 'Not available in data sources.'}
Website:         {company_data.get('website') or 'Not available in data sources.'}
LinkedIn:        {company_data.get('linkedin_url') or 'Not available in data sources.'}
Employees:       {company_data.get('employee_count') or 'Not available in data sources.'}
Revenue (USD):   {str(company_data.get('revenue_usd')) + ' (Wikidata estimate — cross-check with financial snippets)' if company_data.get('revenue_usd') else 'Not available in data sources.'}
Total assets:    {str(company_data.get('total_assets_usd')) + ' (Wikidata estimate)' if company_data.get('total_assets_usd') else 'Not available in data sources.'}
Total funding:   {company_data.get('total_funding_usd') or 'Not available in data sources.'}
Services/specialties: {services_text}

Historical founders (may no longer be active):
{historical_founders_text}

Current leadership (verified active roles):
{current_leadership_text}

Structured contact info:
{contact_struct}

Sources used: {', '.join(company_data.get('sources_used', [])) or 'none'}

=== WEB SNIPPETS — GENERAL ===
{general_snippets or 'No general snippets available.'}

=== WEB SNIPPETS — FINANCIAL (use ONLY these for revenue/funding figures) ===
{financial_snippets or 'No financial snippets available.'}

=== WEB SNIPPETS — CONTACT (use ONLY these for contact details) ===
{contact_snippets or 'No contact snippets available.'}

=== REPORT FORMAT (required — all 6 sections must be present) ===
{"IMPORTANT: The user searched for a PRODUCT. The report must be about the PRODUCT itself." + chr(10) + f"If a parent company is identified above, include it prominently in the Overview section." + chr(10) + "Do NOT write a report about the parent company — write about the product." if is_product_mode else ""}

Write a Markdown report with exactly these 6 sections:

## Overview
[{'Product' if is_product_mode else 'Company'} name, {'parent company (if known), ' if is_product_mode else ''}industry, founding year, HQ, brief description — from structured data only]

## Current Leadership
[Current executives from "Current leadership" field — if empty, write "Not available in data sources."]

## Historical Founders
[From "Historical founders" list — note that founders may no longer be active/associated]

## Products & Services
[{'Core features and capabilities of this product' if is_product_mode else 'From description and general snippets only'}]

## Financials
[Revenue, funding raised, investment rounds, valuation —
 ONLY from financial snippets and structured fields.
 Quote the snippet source inline. If none available, write "Not available in data sources."]

## Contact & Sources
[Email, phone, address — ONLY from structured contact dict and [CONTACT] snippets.
 List all sources used at the end.]

Write the report now — no preamble, no code fences:"""

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
    response = await llm.ainvoke(messages)
    report_text = _content_str(response.content).strip()

    # Strip markdown code fences if the LLM wrapped the output
    if report_text.startswith("```"):
        lines = report_text.splitlines()
        report_text = "\n".join(
            lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        ).strip()

    # Extract token usage from response metadata.
    # Ollama uses prompt_eval_count / eval_count; OpenAI-compat uses prompt_tokens / completion_tokens.
    meta: dict[str, Any] = response.response_metadata or {}
    usage: dict[str, Any] = meta.get("usage", {})
    token_in: int = (
        usage.get("prompt_tokens")          # OpenAI / Anthropic compat
        or meta.get("prompt_eval_count")    # Ollama native
        or 0
    )
    token_out: int = (
        usage.get("completion_tokens")      # OpenAI / Anthropic compat
        or meta.get("eval_count")           # Ollama native
        or 0
    )

    return {
        "scrape_results": raw_results,
        "company_data": company_data,
        "report_text": report_text,
        "attempt_number": attempt,
        "token_count_in": token_in,
        "token_count_out": token_out,
    }


# ---------------------------------------------------------------------------
# Node 4: validate_and_store
# Validates the report via Langfuse, stores to DB + Qdrant if passed.
# ---------------------------------------------------------------------------
async def validate_and_store(state: AgentState) -> dict:
    from langfuse_client import validate_report
    from qdrant_store import upsert_report
    import db

    report_text = state.get("report_text", "")
    company_name = state.get("company_name", "")
    attempt = state.get("attempt_number", 1)

    _emit(state, "validating", f"Validating report quality (attempt {attempt}).")

    trace_id = state.get("langfuse_trace_id") or ""
    passed, relevancy, feedback = await validate_report(
        report_text=report_text,
        company_name=company_name,
        trace_id=trace_id,
    )

    if not passed and attempt < settings.VALIDATION_MAX_RETRIES:
        _emit(state, "retry", f"Validation failed (relevancy={relevancy:.2f}). Retrying...")
        await db.update_session(state["session_id"], retry_count=attempt)
        return {
            "validation_passed": False,
            "relevancy_score": relevancy,
            "validation_feedback": feedback,
        }

    # Either passed or max retries reached — store result
    _emit(state, "storing", "Storing report in database and vector store.")

    report_data: dict[str, Any] = {
        **state.get("company_data", {}),
        "report_text": report_text,
        "validation_passed": passed,
        "relevancy_score": relevancy,
        "token_count_in": state.get("token_count_in"),
        "token_count_out": state.get("token_count_out"),
    }

    report_id = await db.create_report(state["session_id"], report_data)

    # Upsert into Qdrant, then write the point_id back to the DB row
    qdrant_point_id = await upsert_report(
        report_id=report_id,
        report_text=report_text,
        company_data=state.get("company_data", {}),
    )
    if qdrant_point_id:
        await db.update_report(report_id, qdrant_point_id=qdrant_point_id)

    await db.update_session(
        state["session_id"],
        status="complete",
    )

    _emit(state, "complete", "Research complete.", report_id=report_id)

    return {
        "validation_passed": passed,
        "relevancy_score": relevancy,
        "report_id": report_id,
        "qdrant_point_id": qdrant_point_id,
    }


# ---------------------------------------------------------------------------
# Node 5: emit_error  (invalid input or unrecoverable failure)
# ---------------------------------------------------------------------------
async def emit_error(state: AgentState) -> dict:
    import db
    msg = state.get("error_message", "Invalid input.")
    _emit(state, "error", msg)
    await db.update_session(state["session_id"], status="failed", error_message=msg)
    return {}
