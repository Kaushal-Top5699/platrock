"""
Schema contract tests.

Verifies that every Pydantic model can be instantiated with valid data and
that key constraints (required fields, enum values, defaults) behave as
specified in src/schemas.py.
"""

from datetime import datetime

import pytest

from src.schemas import (
    ComplianceDecision,
    ComplianceInput,
    ComplianceOutput,
    DispatchInput,
    DispatchOutput,
    IntakeInput,
    IntakeOutput,
    IntakeStatus,
    InventoryInput,
    InventoryOutput,
    IssueCategory,
    TenantMessage,
    TriageInput,
    TriageOutput,
    UrgencyLevel,
    WorkflowResult,
)


# ---------------------------------------------------------------------------
# Fixtures — minimal valid instances reused across tests
# ---------------------------------------------------------------------------


@pytest.fixture
def tenant_message():
    return TenantMessage(
        unit_id="C-204",
        tenant_name="Maria Rodriguez",
        raw_message="My AC is blowing warm air.",
    )


@pytest.fixture
def intake_output():
    return IntakeOutput(
        status=IntakeStatus.TICKET_READY,
        ticket_id="TKT-001",
        unit_id="C-204",
        tenant_name="Maria Rodriguez",
        summary="AC unit in C-204 blowing warm air; possible refrigerant or compressor issue.",
        raw_message="My AC is blowing warm air.",
        reasoning="Tenant described cooling failure with no safety risk; sufficient detail for triage.",
    )


@pytest.fixture
def triage_output():
    return TriageOutput(
        ticket_id="TKT-001",
        urgency=UrgencyLevel.MODERATE,
        category=IssueCategory.HVAC,
        likely_root_causes=["refrigerant leak", "failed capacitor"],
        property_history_summary="Filter replaced 6 months ago; no prior cooling failure on record.",
        recommended_skills=["HVAC", "EPA-608"],
        reasoning="DFW summer heat makes cooling failure a quality-of-life issue requiring 48-h response.",
    )


@pytest.fixture
def inventory_output():
    return InventoryOutput(
        ticket_id="TKT-001",
        parts_in_stock=[{"name": "Capacitor 45/5 MFD", "sku": "CAP-455", "quantity": 2}],
        parts_needed_to_order=[],
        can_proceed_today=True,
        reasoning="All likely parts are in on-site inventory; no ordering required.",
    )


@pytest.fixture
def dispatch_output():
    return DispatchOutput(
        ticket_id="TKT-001",
        recommended_vendor_id="V-003",
        recommended_vendor_name="Carlos M.",
        scheduled_window="Today 2–4 PM",
        job_brief_en="HVAC cooling failure in C-204. Check refrigerant level and capacitor. Parts on-site.",
        job_brief_translated="Falla de enfriamiento HVAC en C-204. Verificar nivel de refrigerante y capacitor.",
        translation_language="es",
        estimated_cost_usd=285.00,
        reasoning="Carlos M. holds EPA-608, rates 4.8★, is available today, and prefers Spanish.",
    )


@pytest.fixture
def compliance_output():
    return ComplianceOutput(
        ticket_id="TKT-001",
        decision=ComplianceDecision.APPROVED,
        rules_checked=["CR-001", "CR-002", "CR-003"],
        violations=[],
        recommendation="Dispatch may proceed. All compliance rules satisfied.",
        reasoning="Cost $285 is under $500 ceiling. Vendor EPA-608 certified. No Fair Housing flags.",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnums:
    def test_urgency_levels(self):
        assert list(UrgencyLevel) == [
            UrgencyLevel.EMERGENCY,
            UrgencyLevel.HIGH,
            UrgencyLevel.MODERATE,
            UrgencyLevel.LOW,
        ]

    def test_issue_categories(self):
        expected = {"HVAC", "PLUMBING", "ELECTRICAL", "APPLIANCE", "STRUCTURAL", "PEST", "OTHER"}
        assert {c.value for c in IssueCategory} == expected

    def test_compliance_decisions(self):
        expected = {"APPROVED", "REJECTED", "NEEDS_MANAGER_EXCEPTION"}
        assert {d.value for d in ComplianceDecision} == expected

    def test_intake_status(self):
        assert IntakeStatus.TICKET_READY.value == "TICKET_READY"
        assert IntakeStatus.NEEDS_CLARIFICATION.value == "NEEDS_CLARIFICATION"


class TestTenantMessage:
    def test_constructs(self, tenant_message):
        assert tenant_message.unit_id == "C-204"
        assert tenant_message.language == "en"
        assert isinstance(tenant_message.timestamp, datetime)

    def test_raw_message_max_length(self):
        with pytest.raises(Exception):
            TenantMessage(
                unit_id="A-101",
                tenant_name="Test",
                raw_message="x" * 2001,
            )


class TestIntakeAgent:
    def test_intake_input_constructs(self, tenant_message):
        inp = IntakeInput(message=tenant_message)
        assert inp.message.unit_id == "C-204"

    def test_intake_output_ticket_ready(self, intake_output):
        assert intake_output.status == IntakeStatus.TICKET_READY
        assert intake_output.ticket_id == "TKT-001"
        assert intake_output.clarifying_question is None

    def test_intake_output_needs_clarification(self):
        out = IntakeOutput(
            status=IntakeStatus.NEEDS_CLARIFICATION,
            ticket_id=None,
            unit_id="C-204",
            tenant_name="Maria Rodriguez",
            summary="Possible cooling issue — need more detail.",
            clarifying_question="Is there any water leaking near the unit or unusual sounds?",
            raw_message="AC seems off.",
            reasoning="Message too vague to classify without one follow-up.",
        )
        assert out.ticket_id is None
        assert out.clarifying_question is not None


class TestTriageAgent:
    def test_triage_input_constructs(self, intake_output):
        inp = TriageInput(intake=intake_output)
        assert inp.intake.ticket_id == "TKT-001"

    def test_triage_output_constructs(self, triage_output):
        assert triage_output.urgency == UrgencyLevel.MODERATE
        assert triage_output.category == IssueCategory.HVAC
        assert len(triage_output.likely_root_causes) >= 1
        assert len(triage_output.recommended_skills) >= 1

    def test_triage_output_requires_nonempty_root_causes(self):
        with pytest.raises(Exception):
            TriageOutput(
                ticket_id="TKT-001",
                urgency=UrgencyLevel.LOW,
                category=IssueCategory.OTHER,
                likely_root_causes=[],
                property_history_summary="none",
                recommended_skills=["GENERAL"],
                reasoning="test",
            )


class TestInventoryAgent:
    def test_inventory_input_constructs(self, triage_output):
        inp = InventoryInput(triage=triage_output)
        assert inp.triage.ticket_id == "TKT-001"

    def test_inventory_output_constructs(self, inventory_output):
        assert inventory_output.can_proceed_today is True
        assert inventory_output.parts_needed_to_order == []

    def test_inventory_output_defaults(self):
        out = InventoryOutput(
            ticket_id="TKT-002",
            can_proceed_today=False,
            reasoning="Part not in stock.",
        )
        assert out.parts_in_stock == []
        assert out.parts_needed_to_order == []


class TestDispatchAgent:
    def test_dispatch_input_constructs(self, triage_output, inventory_output):
        inp = DispatchInput(triage=triage_output, inventory=inventory_output)
        assert inp.triage.ticket_id == inp.inventory.ticket_id

    def test_dispatch_output_constructs(self, dispatch_output):
        assert dispatch_output.recommended_vendor_id == "V-003"
        assert dispatch_output.translation_language == "es"
        assert dispatch_output.estimated_cost_usd == 285.00

    def test_dispatch_output_no_translation(self):
        out = DispatchOutput(
            ticket_id="TKT-001",
            recommended_vendor_id="V-001",
            recommended_vendor_name="Bob T.",
            scheduled_window="Tomorrow 9–11 AM",
            job_brief_en="Fix the AC.",
            estimated_cost_usd=150.00,
            reasoning="English-speaking vendor.",
        )
        assert out.job_brief_translated is None
        assert out.translation_language is None

    def test_dispatch_output_rejects_negative_cost(self):
        with pytest.raises(Exception):
            DispatchOutput(
                ticket_id="TKT-001",
                recommended_vendor_id="V-001",
                recommended_vendor_name="Bob T.",
                scheduled_window="Tomorrow 9–11 AM",
                job_brief_en="Fix the AC.",
                estimated_cost_usd=-50.00,
                reasoning="test",
            )


class TestComplianceAuditor:
    def test_compliance_input_constructs(self, dispatch_output):
        inp = ComplianceInput(dispatch=dispatch_output)
        assert inp.dispatch.ticket_id == "TKT-001"

    def test_compliance_output_approved(self, compliance_output):
        assert compliance_output.decision == ComplianceDecision.APPROVED
        assert compliance_output.violations == []

    def test_compliance_output_rejected(self):
        out = ComplianceOutput(
            ticket_id="TKT-001",
            decision=ComplianceDecision.REJECTED,
            rules_checked=["CR-001", "CR-004"],
            violations=["Estimated cost $650 exceeds $500 ceiling (CR-004)"],
            recommendation="Reject dispatch. Obtain manager exception or find lower-cost vendor.",
            reasoning="Cost ceiling breached; veto applied.",
        )
        assert len(out.violations) == 1


class TestWorkflowResult:
    def test_full_workflow_constructs(
        self,
        intake_output,
        triage_output,
        inventory_output,
        dispatch_output,
        compliance_output,
    ):
        result = WorkflowResult(
            ticket_id="TKT-001",
            intake=intake_output,
            triage=triage_output,
            inventory=inventory_output,
            dispatch=dispatch_output,
            compliance=compliance_output,
            final_status="READY_FOR_APPROVAL",
        )
        assert result.ticket_id == "TKT-001"
        assert result.final_status == "READY_FOR_APPROVAL"
        assert result.audit_trail == []

    def test_partial_workflow_constructs(self, intake_output):
        result = WorkflowResult(
            ticket_id="TKT-001",
            intake=intake_output,
            final_status="NEEDS_CLARIFICATION",
        )
        assert result.triage is None
        assert result.compliance is None

    def test_workflow_with_audit_trail(self, intake_output):
        trail = [
            {"agent": "Intake", "timestamp": "2026-04-22T10:00:00", "action": "TICKET_READY"},
        ]
        result = WorkflowResult(
            ticket_id="TKT-001",
            intake=intake_output,
            final_status="NEEDS_CLARIFICATION",
            audit_trail=trail,
        )
        assert len(result.audit_trail) == 1
        assert result.audit_trail[0]["agent"] == "Intake"
