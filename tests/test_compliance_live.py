"""
Live end-to-end tests for the Compliance Auditor.

IMPORTANT: These tests make real Anthropic API calls and cost real money
(approximately $0.02 per full run at Claude Sonnet 4.5 pricing).

Requirements:
  - ANTHROPIC_API_KEY must be set in .env or the environment.
  - Run manually during development; skip in CI by default.

Design note: the APPROVED path is fully deterministic given the fixture values
($293 cost, EPA-608 certified vendor, MODERATE urgency, valid ticket_id), so
the decision assertion is reliable despite non-deterministic LLM output.
"""

import json
import os

import pytest

from src.agents.compliance import run_compliance_agent
from src.schemas import (
    ComplianceDecision,
    ComplianceOutput,
    DispatchOutput,
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
def dispatch_fixture():
    return DispatchOutput(
        ticket_id="TKT-test-comp",
        recommended_vendor_id="V001",
        recommended_vendor_name="Carlos M.",
        scheduled_window="Today 2-4 PM",
        job_brief_en="HVAC check required.",
        job_brief_translated="Se requiere revisión de HVAC.",
        translation_language="Spanish",
        estimated_cost_usd=293.0,
        reasoning="Carlos selected.",
    )


@pytest.fixture
def triage_fixture():
    return TriageOutput(
        ticket_id="TKT-test-comp",
        urgency=UrgencyLevel.MODERATE,
        category=IssueCategory.HVAC,
        likely_root_causes=["Low refrigerant"],
        property_history_summary="Filter replaced.",
        recommended_skills=["HVAC", "EPA-608"],
        reasoning="MODERATE.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_compliance_agent_approves_valid_dispatch(dispatch_fixture, triage_fixture):
    """$293 cost, EPA-608 certified, MODERATE urgency — all rules should pass."""
    with open("data/compliance_rules.json") as f:
        raw = json.load(f)
    rules = raw["compliance_rules"]

    vendor_certifications = ["EPA-608", "NATE-HVAC"]

    result = run_compliance_agent(
        dispatch_fixture, triage_fixture, vendor_certifications, rules
    )

    print("\n--- Compliance Auditor Live Output ---")
    print(f"ticket_id:     {result.ticket_id}")
    print(f"decision:      {result.decision}")
    print(f"rules_checked: {result.rules_checked}")
    print(f"violations:    {result.violations}")
    print(f"recommendation:{result.recommendation}")
    print(f"reasoning:     {result.reasoning}")
    print("--------------------------------------")

    assert isinstance(result, ComplianceOutput)
    assert result.ticket_id == "TKT-test-comp"
    assert result.decision == ComplianceDecision.APPROVED
    assert "CR-001" in result.rules_checked
    assert "CR-002" in result.rules_checked
    assert result.violations == []
    assert len(result.recommendation) > 10
    assert len(result.reasoning) > 20
