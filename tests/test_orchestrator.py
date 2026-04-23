"""
End-to-end integration test for the PlatRock LangGraph orchestrator.

IMPORTANT: This test makes 5 real Anthropic API calls (intake + triage +
inventory + dispatch + compliance) and costs approximately $0.10.

Requirements:
  - ANTHROPIC_API_KEY must be set in .env or the environment.
  - Run manually during development; skip in CI by default.

This is the full Maria / AC demo scenario that will be presented at Wipro.
"""

import os

import pytest

from src.orchestrator import run_workflow
from src.schemas import WorkflowResult

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="Requires ANTHROPIC_API_KEY in environment for live LLM tests",
)


def test_full_workflow_maria_ac_scenario():
    """Full pipeline: Maria's AC report → READY_FOR_APPROVAL with Carlos M. dispatched."""
    result = run_workflow(
        unit_id="C-204",
        tenant_name="Maria Rodriguez",
        raw_message=(
            "My AC is blowing warm air and it started this morning. "
            "The thermostat is set to 72 but it feels like 80 in the apartment."
        ),
    )

    print("\n=== Full Workflow Result ===")
    print(f"final_status:     {result.final_status}")
    print(f"ticket_id:        {result.ticket_id}")
    print(f"--- Intake ---")
    print(f"  status:         {result.intake.status}")
    print(f"  summary:        {result.intake.summary}")
    print(f"--- Triage ---")
    print(f"  urgency:        {result.triage.urgency}")
    print(f"  category:       {result.triage.category}")
    print(f"  root causes:    {result.triage.likely_root_causes}")
    print(f"--- Inventory ---")
    print(f"  parts_in_stock: {[p['name'] for p in result.inventory.parts_in_stock]}")
    print(f"  proceed_today:  {result.inventory.can_proceed_today}")
    print(f"--- Dispatch ---")
    print(f"  vendor:         {result.dispatch.recommended_vendor_name} ({result.dispatch.recommended_vendor_id})")
    print(f"  window:         {result.dispatch.scheduled_window}")
    print(f"  cost:           ${result.dispatch.estimated_cost_usd}")
    print(f"  translation:    {result.dispatch.translation_language}")
    print(f"--- Compliance ---")
    print(f"  decision:       {result.compliance.decision}")
    print(f"  rules_checked:  {result.compliance.rules_checked}")
    print(f"  recommendation: {result.compliance.recommendation}")
    print(f"--- Audit Trail ({len(result.audit_trail)} entries) ---")
    for entry in result.audit_trail:
        print(f"  {entry['agent']:12} {entry['action']}")
    print("===========================")

    assert isinstance(result, WorkflowResult)
    assert result.final_status == "READY_FOR_APPROVAL"
    assert result.intake is not None
    assert result.triage is not None
    assert result.inventory is not None
    assert result.dispatch is not None
    assert result.compliance is not None
    assert result.compliance.decision.value == "APPROVED"
    assert result.dispatch.recommended_vendor_id == "V001"
    assert len(result.audit_trail) == 5
