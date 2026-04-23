"""
Live end-to-end tests for the Inventory Agent.

IMPORTANT: These tests make real Anthropic API calls and cost real money
(approximately $0.02 per full run at Claude Sonnet 4.5 pricing).

Requirements:
  - ANTHROPIC_API_KEY must be set in .env or the environment.
  - Run manually during development; skip in CI by default.

Design note: assertions check structural properties and the agent's judgment
(parts matched, can_proceed_today) NOT exact wording, because LLM output is
non-deterministic.  Schema validation inside run_inventory_agent() already
guarantees field types; these tests verify domain-level correctness.
"""

import json
import os

import pytest

from src.agents.inventory import run_inventory_agent
from src.schemas import IssueCategory, InventoryOutput, TriageOutput, UrgencyLevel

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY in environment for live LLM tests",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def triage_fixture():
    return TriageOutput(
        ticket_id="TKT-test-inv",
        urgency=UrgencyLevel.MODERATE,
        category=IssueCategory.HVAC,
        likely_root_causes=[
            "Low refrigerant / refrigerant leak",
            "Faulty compressor start capacitor",
        ],
        property_history_summary="Filter replaced Oct 2025.",
        recommended_skills=["HVAC", "EPA-608"],
        reasoning="MODERATE urgency HVAC issue.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_inventory_agent_hvac_parts(triage_fixture):
    """R410A and compressor capacitor are in stock — job should proceed today."""
    with open("data/inventory.json") as f:
        raw = json.load(f)
    inventory_data = raw["inventory"]

    result = run_inventory_agent(triage_fixture, inventory_data)

    print("\n--- Inventory Agent Live Output ---")
    print(f"ticket_id:            {result.ticket_id}")
    print(f"parts_in_stock:       {result.parts_in_stock}")
    print(f"parts_needed_to_order:{result.parts_needed_to_order}")
    print(f"can_proceed_today:    {result.can_proceed_today}")
    print(f"reasoning:            {result.reasoning}")
    print("-----------------------------------")

    assert isinstance(result, InventoryOutput)
    assert result.ticket_id == "TKT-test-inv"
    assert isinstance(result.parts_in_stock, list)
    assert isinstance(result.parts_needed_to_order, list)
    assert result.can_proceed_today is True
    assert len(result.parts_in_stock) >= 1
    assert len(result.reasoning) > 20
