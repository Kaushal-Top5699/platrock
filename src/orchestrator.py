"""
PlatRock Orchestrator — LangGraph workflow wiring all five agents.

Flow: intake → triage → inventory → dispatch → compliance → END

Triage and Inventory are architecturally parallel (neither depends on the
other's output); they run sequentially here for LangGraph stability in the
MVP.  The parallel design is documented in PROJECT.md and can be activated
in production by adding a fan-out node after intake.

State is a TypedDict populated as the graph progresses. All data files are
loaded once at workflow entry and passed through state so individual nodes
never perform I/O.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.agents.compliance import run_compliance_agent
from src.agents.dispatch import run_dispatch_agent
from src.agents.intake import run_intake_agent
from src.agents.inventory import run_inventory_agent
from src.agents.triage import run_triage_agent
from src.schemas import (
    ComplianceDecision,
    ComplianceOutput,
    DispatchOutput,
    IntakeOutput,
    IntakeStatus,
    InventoryOutput,
    TenantMessage,
    TriageOutput,
    WorkflowResult,
)

_DATA_DIR = Path(__file__).parent.parent / "data"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class PlatRockState(TypedDict):
    # Input
    tenant_message: TenantMessage
    # Agent outputs (None until each node runs)
    intake_output: Optional[IntakeOutput]
    triage_output: Optional[TriageOutput]
    inventory_output: Optional[InventoryOutput]
    dispatch_output: Optional[DispatchOutput]
    compliance_output: Optional[ComplianceOutput]
    # Reference data loaded once at workflow entry
    property_history: list
    inventory_data: list
    vendor_data: list
    compliance_rules: list
    # Workflow metadata
    error: Optional[str]
    final_status: str  # IN_PROGRESS | NEEDS_CLARIFICATION | READY_FOR_APPROVAL | BLOCKED | ERROR


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_data_files() -> dict:
    """Load all four reference data files. Returns a dict keyed by data type."""
    with open(_DATA_DIR / "property_history.json") as f:
        ph = json.load(f)
    with open(_DATA_DIR / "inventory.json") as f:
        inv = json.load(f)
    with open(_DATA_DIR / "vendors.json") as f:
        ven = json.load(f)
    with open(_DATA_DIR / "compliance_rules.json") as f:
        cr = json.load(f)
    return {
        "property_history": ph["property_history"],
        "inventory": inv["inventory"],
        "vendors": ven["vendors"],
        "compliance_rules": cr["compliance_rules"],
    }


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def intake_node(state: PlatRockState) -> dict:
    try:
        result = run_intake_agent(state["tenant_message"])
        if result.status == IntakeStatus.NEEDS_CLARIFICATION:
            return {"intake_output": result, "final_status": "NEEDS_CLARIFICATION"}
        return {"intake_output": result}
    except Exception as exc:
        return {"error": str(exc), "final_status": "ERROR"}


def triage_node(state: PlatRockState) -> dict:
    if state.get("final_status") == "ERROR":
        return {}
    try:
        unit_id = state["intake_output"].unit_id
        filtered = next(
            (entry["records"] for entry in state["property_history"] if entry["unit"] == unit_id),
            [],
        )
        result = run_triage_agent(state["intake_output"], filtered)
        return {"triage_output": result}
    except Exception as exc:
        return {"error": str(exc), "final_status": "ERROR"}


def inventory_node(state: PlatRockState) -> dict:
    if state.get("final_status") == "ERROR":
        return {}
    try:
        result = run_inventory_agent(state["triage_output"], state["inventory_data"])
        return {"inventory_output": result}
    except Exception as exc:
        return {"error": str(exc), "final_status": "ERROR"}


def dispatch_node(state: PlatRockState) -> dict:
    if state.get("final_status") == "ERROR":
        return {}
    try:
        result = run_dispatch_agent(
            state["triage_output"],
            state["inventory_output"],
            state["vendor_data"],
        )
        return {"dispatch_output": result}
    except Exception as exc:
        return {"error": str(exc), "final_status": "ERROR"}


def compliance_node(state: PlatRockState) -> dict:
    if state.get("final_status") == "ERROR":
        return {}
    try:
        vendor_id = state["dispatch_output"].recommended_vendor_id
        vendor = next((v for v in state["vendor_data"] if v["id"] == vendor_id), None)
        vendor_certs = vendor.get("certifications", []) if vendor else []

        result = run_compliance_agent(
            state["dispatch_output"],
            state["triage_output"],
            vendor_certs,
            state["compliance_rules"],
        )
        final_status = "READY_FOR_APPROVAL" if result.decision == ComplianceDecision.APPROVED else "BLOCKED"
        return {"compliance_output": result, "final_status": final_status}
    except Exception as exc:
        return {"error": str(exc), "final_status": "ERROR"}


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------


def _route_after_intake(state: PlatRockState) -> str:
    if state.get("final_status") in ("NEEDS_CLARIFICATION", "ERROR"):
        return END
    return "triage"


def build_graph():
    """Construct and compile the PlatRock LangGraph workflow."""
    workflow = StateGraph(PlatRockState)

    workflow.add_node("intake", intake_node)
    workflow.add_node("triage", triage_node)
    workflow.add_node("inventory", inventory_node)
    workflow.add_node("dispatch", dispatch_node)
    workflow.add_node("compliance", compliance_node)

    workflow.set_entry_point("intake")

    # After intake: stop early on NEEDS_CLARIFICATION/ERROR, else continue.
    workflow.add_conditional_edges("intake", _route_after_intake)
    workflow.add_edge("triage", "inventory")
    workflow.add_edge("inventory", "dispatch")
    workflow.add_edge("dispatch", "compliance")
    workflow.add_edge("compliance", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_workflow(unit_id: str, tenant_name: str, raw_message: str) -> WorkflowResult:
    """
    Run the full PlatRock pipeline for a tenant maintenance report.

    Loads all reference data, invokes the 5-agent LangGraph workflow, and
    returns a WorkflowResult with every agent's output and the final status.
    """
    data = load_data_files()

    initial_state: PlatRockState = {
        "tenant_message": TenantMessage(
            unit_id=unit_id,
            tenant_name=tenant_name,
            raw_message=raw_message,
        ),
        "intake_output": None,
        "triage_output": None,
        "inventory_output": None,
        "dispatch_output": None,
        "compliance_output": None,
        "property_history": data["property_history"],
        "inventory_data": data["inventory"],
        "vendor_data": data["vendors"],
        "compliance_rules": data["compliance_rules"],
        "error": None,
        "final_status": "IN_PROGRESS",
    }

    final_state = build_graph().invoke(initial_state)

    audit_trail = [
        {
            "agent": name,
            "timestamp": datetime.now().isoformat(),
            "action": f"{name}_completed",
        }
        for name, output in [
            ("intake", final_state.get("intake_output")),
            ("triage", final_state.get("triage_output")),
            ("inventory", final_state.get("inventory_output")),
            ("dispatch", final_state.get("dispatch_output")),
            ("compliance", final_state.get("compliance_output")),
        ]
        if output is not None
    ]

    intake = final_state.get("intake_output")
    ticket_id = intake.ticket_id if (intake and intake.ticket_id) else "PENDING"

    return WorkflowResult(
        ticket_id=ticket_id,
        intake=intake,
        triage=final_state.get("triage_output"),
        inventory=final_state.get("inventory_output"),
        dispatch=final_state.get("dispatch_output"),
        compliance=final_state.get("compliance_output"),
        final_status=final_state["final_status"],
        audit_trail=audit_trail,
    )
