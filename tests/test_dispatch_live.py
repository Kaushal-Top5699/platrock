"""
Live end-to-end tests for the Dispatch Agent.

IMPORTANT: These tests make real Anthropic API calls and cost real money
(approximately $0.02 per full run at Claude Sonnet 4.5 pricing).

Requirements:
  - ANTHROPIC_API_KEY must be set in .env or the environment.
  - Run manually during development; skip in CI by default.

Design note: assertions check structural properties and the agent's judgment
(vendor selection, translation, cost) NOT exact wording. Carlos M. (V001) is
the only EPA-608-certified HVAC vendor available today, making the vendor
selection deterministic even though the LLM output is otherwise non-deterministic.
"""

import json
import os

import pytest

from src.agents.dispatch import run_dispatch_agent
from src.schemas import (
    DispatchOutput,
    InventoryOutput,
    IssueCategory,
    TriageOutput,
    UrgencyLevel,
)

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
        ticket_id="TKT-test-disp",
        urgency=UrgencyLevel.MODERATE,
        category=IssueCategory.HVAC,
        likely_root_causes=["Low refrigerant", "Failed capacitor"],
        property_history_summary="Filter replaced Oct 2025.",
        recommended_skills=["HVAC", "EPA-608"],
        reasoning="MODERATE HVAC.",
    )


@pytest.fixture
def inventory_fixture():
    return InventoryOutput(
        ticket_id="TKT-test-disp",
        parts_in_stock=[
            {"part_id": "P001", "name": "Refrigerant R410A", "quantity_available": 4},
            {"part_id": "P002", "name": "Compressor Start Capacitor", "quantity_available": 6},
        ],
        parts_needed_to_order=[],
        can_proceed_today=True,
        reasoning="Both parts in stock.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_dispatch_agent_selects_carlos(triage_fixture, inventory_fixture):
    """Carlos M. (V001) is the only EPA-608-certified HVAC vendor available today."""
    with open("data/vendors.json") as f:
        raw = json.load(f)
    vendors_data = raw["vendors"]

    result = run_dispatch_agent(triage_fixture, inventory_fixture, vendors_data)

    print("\n--- Dispatch Agent Live Output ---")
    print(f"ticket_id:            {result.ticket_id}")
    print(f"vendor_id:            {result.recommended_vendor_id}")
    print(f"vendor_name:          {result.recommended_vendor_name}")
    print(f"scheduled_window:     {result.scheduled_window}")
    print(f"estimated_cost_usd:   {result.estimated_cost_usd}")
    print(f"translation_language: {result.translation_language}")
    print(f"job_brief_en:\n  {result.job_brief_en}")
    print(f"job_brief_translated:\n  {result.job_brief_translated}")
    print(f"reasoning:            {result.reasoning}")
    print("----------------------------------")

    assert isinstance(result, DispatchOutput)
    assert result.ticket_id == "TKT-test-disp"
    assert result.recommended_vendor_id == "V001"
    assert result.recommended_vendor_name == "Carlos M."
    assert "Today" in result.scheduled_window
    assert result.job_brief_en is not None and len(result.job_brief_en) > 20
    assert result.job_brief_translated is not None
    assert result.translation_language == "Spanish"
    assert result.estimated_cost_usd > 0
    assert result.estimated_cost_usd < 500
    assert len(result.reasoning) > 20
