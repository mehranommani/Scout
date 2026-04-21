"""
Unit tests for agent classification and validation logic.
Uses mocked LLM responses to avoid requiring a running Ollama instance.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.state import AgentState


# ---------------------------------------------------------------------------
# classify_input node
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_company():
    """Valid company name should be classified as 'company'."""
    from agent.nodes import classify_input

    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"type": "company", "canonical_name": "Stripe Inc", "reason": "Well-known payment company."}'

    with patch("agent.nodes.llm") as mock_llm, \
         patch("agent.nodes.call_tool_data", new=AsyncMock(return_value={"likely_valid": True, "reason": "OK"})):
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        state: AgentState = {"raw_input": "Stripe Inc", "session_id": "test-123"}
        result = await classify_input(state)

    assert result["input_type"] == "company"
    assert result["company_name"] == "Stripe Inc"


@pytest.mark.asyncio
async def test_classify_product():
    """Product name should be classified as 'product'."""
    from agent.nodes import classify_input

    mock_llm_response = MagicMock()
    mock_llm_response.content = '{"type": "product", "canonical_name": "iPhone", "reason": "Apple product."}'

    with patch("agent.nodes.llm") as mock_llm, \
         patch("agent.nodes.call_tool_data", new=AsyncMock(return_value={"likely_valid": True, "reason": "OK"})):
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        state: AgentState = {"raw_input": "iPhone", "session_id": "test-456"}
        result = await classify_input(state)

    assert result["input_type"] == "product"


@pytest.mark.asyncio
async def test_classify_invalid_personal_name():
    """Personal name should be rejected by the heuristic before LLM call."""
    from agent.nodes import classify_input

    with patch("agent.nodes.call_tool_data", new=AsyncMock(return_value={
        "likely_valid": False,
        "reason": "Looks like a personal name."
    })):
        state: AgentState = {"raw_input": "John Smith Jr", "session_id": "test-789"}
        result = await classify_input(state)

    assert result["input_type"] == "invalid"
    assert "personal name" in result["error_message"].lower()


@pytest.mark.asyncio
async def test_classify_handles_llm_bad_json():
    """LLM returning invalid JSON should default to 'invalid'."""
    from agent.nodes import classify_input

    mock_llm_response = MagicMock()
    mock_llm_response.content = "I cannot classify this."

    with patch("agent.nodes.llm") as mock_llm, \
         patch("agent.nodes.call_tool_data", new=AsyncMock(return_value={"likely_valid": True, "reason": "OK"})):
        mock_llm.ainvoke = AsyncMock(return_value=mock_llm_response)

        state: AgentState = {"raw_input": "maybe company", "session_id": "test-000"}
        result = await classify_input(state)

    assert result["input_type"] == "invalid"


# ---------------------------------------------------------------------------
# validate_report (langfuse_client)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_validate_report_passes():
    """Well-formed report with all 6 required sections should pass validation."""
    from langfuse_client import validate_report

    report = """## Overview
Stripe, Inc. is an American financial technology company headquartered in
San Francisco, California. Founded in 2010, it provides payment processing
software and APIs for e-commerce websites and mobile applications.
Stripe operates in over 46 countries and serves millions of businesses
ranging from startups to Fortune 500 companies.

## Current Leadership
Patrick Collison serves as CEO and John Collison as President.
Both brothers continue to lead the company they co-founded.

## Historical Founders
Patrick Collison and John Collison co-founded Stripe in 2010 while
students at MIT. They are brothers originally from Limerick, Ireland.

## Products & Services
Stripe offers online payment processing, subscription billing, fraud
detection (Radar), identity verification, revenue reporting, and
Stripe Connect for marketplace platforms.

## Financials
Total funding exceeds $2.2 billion across multiple rounds. The company
was last valued at $65 billion. Annual revenue is estimated above $14B.

## Contact & Sources
Website: https://stripe.com  |  LinkedIn: linkedin.com/company/stripe
Sources: wikidata, opencorporates, crunchbase
"""

    with patch("langfuse_client.get_langfuse") as mock_lf:
        mock_lf_instance = MagicMock()
        mock_lf.return_value = mock_lf_instance
        span_ctx = MagicMock()
        span_ctx.__enter__ = MagicMock(return_value=MagicMock())
        span_ctx.__exit__ = MagicMock(return_value=False)
        mock_lf_instance.start_as_current_observation.return_value = span_ctx

        passed, score, feedback = await validate_report(report, "Stripe")

    assert passed is True
    assert score >= 0.65
    assert feedback == ""


@pytest.mark.asyncio
async def test_validate_report_fails_too_short():
    """Short report should fail length check."""
    from langfuse_client import validate_report

    short_report = "## Overview\nStripe is a company.\n## Current Leadership\nPatrick."

    with patch("langfuse_client.get_langfuse") as mock_lf:
        mock_lf_instance = MagicMock()
        mock_lf.return_value = mock_lf_instance
        span_ctx = MagicMock()
        span_ctx.__enter__ = MagicMock(return_value=MagicMock())
        span_ctx.__exit__ = MagicMock(return_value=False)
        mock_lf_instance.start_as_current_observation.return_value = span_ctx

        result = await validate_report(short_report, "Stripe")
        passed, feedback = result[0], result[2]

    assert passed is False
    assert "short" in feedback.lower() or "minimum" in feedback.lower()


@pytest.mark.asyncio
async def test_validate_report_fails_missing_sections():
    """Report missing required sections should fail structural validation."""
    from langfuse_client import validate_report

    # Has Overview and Products & Services but is missing Current Leadership,
    # Historical Founders, Financials, and Contact & Sources.
    incomplete_report = (
        "## Overview\n" + ("x " * 300) + "\n"
        "## Products & Services\nStripe offers payment APIs and more services.\n"
    )

    with patch("langfuse_client.get_langfuse") as mock_lf:
        mock_lf_instance = MagicMock()
        mock_lf.return_value = mock_lf_instance
        span_ctx = MagicMock()
        span_ctx.__enter__ = MagicMock(return_value=MagicMock())
        span_ctx.__exit__ = MagicMock(return_value=False)
        mock_lf_instance.start_as_current_observation.return_value = span_ctx

        result = await validate_report(incomplete_report, "Stripe")
        passed, feedback = result[0], result[2]

    assert passed is False
    assert "missing" in feedback.lower() or "section" in feedback.lower()
