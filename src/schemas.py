"""
PlatRock agent I/O contracts.

All inter-agent communication flows through these Pydantic models. No agent
emits free-form text to a downstream agent — only typed instances of these
classes. This is a security boundary: raw tenant input is contained inside
TenantMessage and never propagated further; downstream agents see only
structured, validated fields.

Layout:
  1. Enums
  2. Shared types
  3. Intake Agent
  4. Triage Agent
  5. Inventory Agent
  6. Dispatch Agent
  7. Compliance Auditor
  8. Orchestrator / WorkflowResult
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 1. Enums
# ---------------------------------------------------------------------------


class UrgencyLevel(str, Enum):
    """How quickly a maintenance issue must be addressed."""

    EMERGENCY = "EMERGENCY"   # life/safety risk, act within hours
    HIGH = "HIGH"             # significant habitability impact, same-day
    MODERATE = "MODERATE"     # quality-of-life impact, within 48 h
    LOW = "LOW"               # cosmetic / convenience, scheduled


class IssueCategory(str, Enum):
    """Broad maintenance domain used for vendor skill matching."""

    HVAC = "HVAC"
    PLUMBING = "PLUMBING"
    ELECTRICAL = "ELECTRICAL"
    APPLIANCE = "APPLIANCE"
    STRUCTURAL = "STRUCTURAL"
    PEST = "PEST"
    OTHER = "OTHER"


class ComplianceDecision(str, Enum):
    """Outcome of the Compliance Auditor review."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MANAGER_EXCEPTION = "NEEDS_MANAGER_EXCEPTION"


class IntakeStatus(str, Enum):
    """Whether the Intake Agent has enough information to produce a ticket."""

    TICKET_READY = "TICKET_READY"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"


# ---------------------------------------------------------------------------
# 2. Shared types
# ---------------------------------------------------------------------------


class TenantMessage(BaseModel):
    """Raw inbound message from a tenant before any agent processing.

    This is the only place raw tenant text lives. All downstream agents
    receive structured fields derived from this, never the raw_message itself.
    """

    unit_id: str = Field(..., description="Property unit identifier, e.g. 'C-204'")
    tenant_name: str = Field(..., description="Tenant's display name for UI and manager view")
    raw_message: str = Field(
        ...,
        max_length=2000,
        description="Unmodified text submitted by the tenant (2 000-char cap, security boundary)",
    )
    language: str = Field(
        default="en",
        description="BCP-47 language tag detected or supplied by the UI, e.g. 'en', 'es'",
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Wall-clock time the message was received",
    )


# ---------------------------------------------------------------------------
# 3. Intake Agent
# ---------------------------------------------------------------------------


class IntakeInput(BaseModel):
    """Input envelope for the Intake Agent."""

    message: TenantMessage = Field(..., description="The raw tenant message to process")


class IntakeOutput(BaseModel):
    """Structured ticket produced (or clarification requested) by the Intake Agent.

    When status is NEEDS_CLARIFICATION, ticket_id is None and clarifying_question
    is populated. The Orchestrator will surface the question to the tenant and
    re-invoke Intake with the follow-up answer.
    """

    status: IntakeStatus = Field(..., description="Whether the ticket is ready or needs a follow-up")
    ticket_id: Optional[str] = Field(
        default=None,
        description="Unique ticket identifier assigned by Intake; None until TICKET_READY",
    )
    unit_id: str = Field(..., description="Unit identifier copied from the inbound message")
    tenant_name: str = Field(..., description="Tenant name copied from the inbound message")
    summary: str = Field(
        ...,
        description="Intake Agent's concise, jargon-free restatement of the reported issue",
    )
    clarifying_question: Optional[str] = Field(
        default=None,
        description="Single follow-up question for the tenant; populated only when NEEDS_CLARIFICATION",
    )
    raw_message: str = Field(
        ...,
        description="Verbatim copy of the original tenant message preserved for the audit trail",
    )
    reasoning: str = Field(
        ...,
        description="Intake Agent's internal reasoning trace explaining its decisions",
    )


# ---------------------------------------------------------------------------
# 4. Triage Agent
# ---------------------------------------------------------------------------


class TriageInput(BaseModel):
    """Input envelope for the Triage Agent."""

    intake: IntakeOutput = Field(..., description="The completed intake ticket to evaluate")


class TriageOutput(BaseModel):
    """Urgency scoring, issue classification, and recommended resource plan.

    Produced by the Triage Agent after consulting property history. Runs in
    parallel with the Inventory Agent — neither depends on the other's output.
    """

    ticket_id: str = Field(..., description="Ticket identifier, propagated from IntakeOutput")
    urgency: UrgencyLevel = Field(..., description="Urgency score assigned by the Triage Agent")
    category: IssueCategory = Field(..., description="Maintenance domain classification")
    likely_root_causes: List[str] = Field(
        ...,
        min_length=1,
        description="Top 2–3 root-cause hypotheses ranked by likelihood, e.g. ['refrigerant leak', 'failed capacitor']",
    )
    property_history_summary: str = Field(
        ...,
        description="Relevant prior work orders or patterns found in property history",
    )
    recommended_skills: List[str] = Field(
        ...,
        min_length=1,
        description="Vendor certifications / skills required, e.g. ['HVAC', 'EPA-608']",
    )
    reasoning: str = Field(
        ...,
        description="Triage Agent's reasoning trace covering urgency score and classification",
    )


# ---------------------------------------------------------------------------
# 5. Inventory Agent
# ---------------------------------------------------------------------------


class InventoryInput(BaseModel):
    """Input envelope for the Inventory Agent."""

    triage: TriageOutput = Field(..., description="Triage output supplying the parts estimate")


class InventoryOutput(BaseModel):
    """Stock check result for the parts identified by the Triage Agent.

    Runs in parallel with the Triage Agent's property-history lookup phase.
    can_proceed_today drives scheduling logic in the Dispatch Agent.
    """

    ticket_id: str = Field(..., description="Ticket identifier, propagated from TriageOutput")
    parts_in_stock: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Parts confirmed available in on-site inventory, each as {name, sku, quantity}",
    )
    parts_needed_to_order: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Parts that must be sourced externally before work can begin, each as {name, sku, estimated_eta}",
    )
    can_proceed_today: bool = Field(
        ...,
        description="True when all required parts are in stock or same-day delivery is confirmed",
    )
    reasoning: str = Field(
        ...,
        description="Inventory Agent's reasoning trace explaining the stock check outcome",
    )


# ---------------------------------------------------------------------------
# 6. Dispatch Agent
# ---------------------------------------------------------------------------


class DispatchInput(BaseModel):
    """Input envelope for the Dispatch Agent.

    Combines Triage output (skills, urgency) with Inventory output
    (parts availability, can_proceed_today) to inform vendor selection
    and scheduling.
    """

    triage: TriageOutput = Field(..., description="Triage output for skill and urgency requirements")
    inventory: InventoryOutput = Field(..., description="Inventory output for parts and scheduling feasibility")


class DispatchOutput(BaseModel):
    """Vendor match and job brief produced by the Dispatch Agent.

    job_brief_translated and translation_language are None when the matched
    vendor's preferred language is English.
    """

    ticket_id: str = Field(..., description="Ticket identifier, propagated from TriageOutput")
    recommended_vendor_id: str = Field(..., description="Vendor's unique identifier from vendors.json")
    recommended_vendor_name: str = Field(..., description="Human-readable vendor name for the manager UI")
    scheduled_window: str = Field(
        ...,
        description="Proposed appointment window in plain English, e.g. 'Today 2–4 PM'",
    )
    job_brief_en: str = Field(
        ...,
        description="Full job brief in English: issue description, required skills, parts on-site, access notes",
    )
    job_brief_translated: Optional[str] = Field(
        default=None,
        description="Job brief translated into the vendor's preferred language; None for English-speaking vendors",
    )
    translation_language: Optional[str] = Field(
        default=None,
        description="BCP-47 tag for the translated brief, e.g. 'es'; None if no translation was produced",
    )
    estimated_cost_usd: float = Field(
        ...,
        ge=0,
        description="Estimated total cost in USD (labour + parts); used by Compliance Auditor against cost ceiling",
    )
    reasoning: str = Field(
        ...,
        description="Dispatch Agent's reasoning trace covering vendor selection and scheduling decision",
    )


# ---------------------------------------------------------------------------
# 7. Compliance Auditor
# ---------------------------------------------------------------------------


class ComplianceInput(BaseModel):
    """Input envelope for the Compliance Auditor."""

    dispatch: DispatchOutput = Field(..., description="Proposed dispatch to evaluate against compliance rules")


class ComplianceOutput(BaseModel):
    """Compliance verdict with full audit evidence.

    The Compliance Auditor has hard veto power. A REJECTED decision cannot
    be overridden by any other agent or by the Orchestrator — it must surface
    to the property manager unchanged.
    """

    ticket_id: str = Field(..., description="Ticket identifier, propagated from DispatchOutput")
    decision: ComplianceDecision = Field(..., description="Final compliance verdict")
    rules_checked: List[str] = Field(
        ...,
        min_length=1,
        description="Rule IDs evaluated during this audit, e.g. ['CR-001', 'CR-002', 'CR-003']",
    )
    violations: List[str] = Field(
        default_factory=list,
        description="Human-readable violation descriptions; empty list when decision is APPROVED",
    )
    recommendation: str = Field(
        ...,
        description="Plain-English guidance for the property manager on what action to take",
    )
    reasoning: str = Field(
        ...,
        description="Compliance Auditor's reasoning trace over each rule checked",
    )


# ---------------------------------------------------------------------------
# 8. Orchestrator / final workflow result
# ---------------------------------------------------------------------------


class WorkflowResult(BaseModel):
    """Aggregated output of the entire multi-agent workflow.

    This is what the Streamlit UI consumes. Optional fields are None when
    the workflow was interrupted (e.g. compliance rejection before dispatch,
    or intake still awaiting clarification).

    final_status drives the UI state:
      - READY_FOR_APPROVAL  → show APPROVE / REJECT card to property manager
      - BLOCKED             → show violation details, no approval path
      - NEEDS_CLARIFICATION → surface clarifying_question to tenant
    """

    ticket_id: str = Field(..., description="Canonical ticket identifier for this workflow run")
    intake: IntakeOutput = Field(..., description="Intake Agent output")
    triage: Optional[TriageOutput] = Field(default=None, description="Triage Agent output; None if workflow stopped at intake")
    inventory: Optional[InventoryOutput] = Field(default=None, description="Inventory Agent output; None if workflow stopped before triage")
    dispatch: Optional[DispatchOutput] = Field(default=None, description="Dispatch Agent output; None if workflow stopped before dispatch")
    compliance: Optional[ComplianceOutput] = Field(default=None, description="Compliance Auditor output; None if workflow stopped before compliance")
    final_status: str = Field(
        ...,
        description="Terminal workflow state: 'READY_FOR_APPROVAL' | 'BLOCKED' | 'NEEDS_CLARIFICATION'",
    )
    audit_trail: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Ordered list of {agent, timestamp, action} events for the immutable audit log",
    )
