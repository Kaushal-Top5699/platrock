"""
Live end-to-end tests for the Triage Agent.

IMPORTANT: These tests make real Anthropic API calls and cost real money
(approximately $0.02 per full run at Claude Sonnet 4.5 pricing).

Requirements:
  - ANTHROPIC_API_KEY must be set in .env or the environment.
  - Run manually during development; skip in CI by default.

Design note: assertions check structural properties and the agent's judgment
(urgency, category, required fields) NOT exact wording, because LLM output
is non-deterministic.  Schema validation inside run_triage_agent() already
guarantees field types; these tests verify domain-level correctness.
"""

import json
import os

import pytest

from src.agents.triage import run_triage_agent
from src.schemas import IntakeOutput, IntakeStatus, IssueCategory, TriageOutput, UrgencyLevel

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY in environment for live LLM tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def intake_fixture():
    return IntakeOutput(
        status=IntakeStatus.TICKET_READY,
        ticket_id="TKT-test-triage",
        unit_id="C-204",
        tenant_name="Maria Rodriguez",
        summary="AC unit blowing warm air despite thermostat at 72°F; issue began this morning.",
        clarifying_question=None,
        raw_message="My AC is blowing warm air...",
        reasoning="Sufficient info provided.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_triage_agent_ac_scenario(intake_fixture):
    """Maria's AC ticket should be classified as HVAC with MODERATE or HIGH urgency."""
    with open("data/property_history.json") as f:
        all_history = json.load(f)

    unit_records = next(
        (
            entry["records"]
            for entry in all_history["property_history"]
            if entry["unit"] == "C-204"
        ),
        [],
    )

    result = run_triage_agent(intake_fixture, unit_records)

    print("\n--- Triage Agent Live Output ---")
    print(f"ticket_id:               {result.ticket_id}")
    print(f"urgency:                 {result.urgency}")
    print(f"category:                {result.category}")
    print(f"likely_root_causes:      {result.likely_root_causes}")
    print(f"property_history_summary:{result.property_history_summary}")
    print(f"recommended_skills:      {result.recommended_skills}")
    print(f"reasoning:               {result.reasoning}")
    print("--------------------------------")

    assert isinstance(result, TriageOutput)
    assert result.ticket_id == "TKT-test-triage"
    assert result.urgency in [UrgencyLevel.MODERATE, UrgencyLevel.HIGH]
    assert result.category == IssueCategory.HVAC
    assert len(result.likely_root_causes) >= 2
    assert len(result.recommended_skills) >= 1
    assert "EPA-608" in result.recommended_skills or "HVAC" in result.recommended_skills
    assert len(result.reasoning) > 20
