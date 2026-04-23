"""
Live end-to-end tests for the Intake Agent.

IMPORTANT: These tests make real Anthropic API calls and cost real money
(approximately $0.02 per full run at Claude Sonnet 4.5 pricing).

Requirements:
  - ANTHROPIC_API_KEY must be set in .env or the environment.
  - Run manually during development; skip in CI by default.

Design note: assertions check structural properties (shape, presence, type)
NOT exact wording, because LLM output is non-deterministic. The schema
validation inside run_intake_agent() already guarantees field types; these
tests verify the agent's judgment (TICKET_READY vs NEEDS_CLARIFICATION)
and that the prompt constraints are being respected.
"""

import os

import pytest

from src.agents.intake import run_intake_agent
from src.schemas import IntakeOutput, IntakeStatus, TenantMessage

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY in environment for live LLM tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def maria_message():
    return TenantMessage(
        unit_id="C-204",
        tenant_name="Maria Rodriguez",
        raw_message=(
            "Hi, my AC is blowing warm air and it started this morning. "
            "The thermostat is set to 72 but it feels like 80 in the apartment. "
            "Please help!"
        ),
    )


@pytest.fixture
def vague_message():
    return TenantMessage(
        unit_id="A-101",
        tenant_name="John Smith",
        raw_message="Something is broken.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_intake_agent_ticket_ready(maria_message):
    """Maria's detailed AC message should produce a structured ticket."""
    result = run_intake_agent(maria_message)

    # Type contract
    assert isinstance(result, IntakeOutput)

    # Status
    assert result.status == IntakeStatus.TICKET_READY

    # Ticket ID generated
    assert result.ticket_id is not None
    assert result.ticket_id.startswith("TKT-")

    # Input data preserved exactly
    assert result.unit_id == "C-204"
    assert result.tenant_name == "Maria Rodriguez"
    assert result.raw_message == maria_message.raw_message

    # Summary and reasoning are substantive
    assert result.summary is not None
    assert len(result.summary) > 20, "Summary too short to be useful"
    assert result.reasoning is not None
    assert len(result.reasoning) > 20, "Reasoning too short to be useful"

    # No clarifying question on a ready ticket
    assert result.clarifying_question is None


def test_intake_agent_needs_clarification(vague_message):
    """A vague message should trigger exactly one clarifying question."""
    result = run_intake_agent(vague_message)

    # Type contract
    assert isinstance(result, IntakeOutput)

    # Status
    assert result.status == IntakeStatus.NEEDS_CLARIFICATION

    # No ticket_id until clarification is resolved
    assert result.ticket_id is None

    # Input data preserved exactly
    assert result.unit_id == "A-101"
    assert result.tenant_name == "John Smith"

    # Clarifying question present and well-formed
    assert result.clarifying_question is not None
    assert len(result.clarifying_question) > 10, "Clarifying question too short"
    assert result.clarifying_question.endswith("?"), "Should end with a question mark"

    # Reasoning populated
    assert result.reasoning is not None
    assert len(result.reasoning) > 20
