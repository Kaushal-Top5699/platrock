import streamlit as st

from src.orchestrator import run_workflow

st.set_page_config(page_title="PlatRock", layout="wide", page_icon="🪨")

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

left, right = st.columns([0.4, 0.6])

# ---------------------------------------------------------------------------
# Left panel — Tenant Input
# ---------------------------------------------------------------------------

with left:
    st.title("🪨 PlatRock")
    st.subheader("Multi-Agent Property Management")

    unit_id = st.text_input("Unit ID", value="C-204")
    tenant_name = st.text_input("Tenant Name", value="Maria Rodriguez")
    raw_message = st.text_area(
        "Maintenance Request",
        value=(
            "My AC is blowing warm air and it started this morning. "
            "The thermostat is set to 72 but it feels like 80 in the apartment."
        ),
        height=120,
    )

    if st.button("🚀 Run PlatRock", type="primary"):
        if not unit_id.strip() or not tenant_name.strip() or not raw_message.strip():
            st.error("All fields are required.")
        else:
            st.session_state.pop("result", None)
            st.session_state.pop("error", None)
            with st.spinner("Running 5 agents..."):
                try:
                    result = run_workflow(unit_id.strip(), tenant_name.strip(), raw_message.strip())
                    st.session_state["result"] = result
                except Exception as exc:
                    st.session_state["error"] = str(exc)

    st.info("Demo: Pre-filled with Maria Rodriguez / Unit C-204 / AC issue")

# ---------------------------------------------------------------------------
# Right panel — Results
# ---------------------------------------------------------------------------

with right:
    result = st.session_state.get("result")
    error = st.session_state.get("error")

    if error:
        st.error(f"Pipeline error: {error}")
    elif result is None:
        st.info("Submit a maintenance request to see PlatRock in action.")
    else:
        # --- Section 1: Status Banner ---
        if result.final_status == "READY_FOR_APPROVAL":
            st.success("✅ READY FOR APPROVAL")
        elif result.final_status == "BLOCKED":
            st.error("🚫 BLOCKED — Compliance violation")
        elif result.final_status == "NEEDS_CLARIFICATION":
            st.warning("❓ Needs clarification from tenant")

        # --- Section 2: Agent Activity Dashboard ---
        st.subheader("🤖 Agent Activity")

        # Card 1 — Intake
        with st.expander("Intake Agent — " + (result.intake.status.value if result.intake else "NOT RUN"), expanded=True):
            if result.intake:
                st.write(f"**Status:** {result.intake.status.value}")
                st.write(f"**Ticket ID:** {result.intake.ticket_id or 'Pending clarification'}")
                st.write(f"**Summary:** {result.intake.summary}")
                if result.intake.clarifying_question:
                    st.warning(f"**Clarifying Question:** {result.intake.clarifying_question}")
                with st.expander("Reasoning", expanded=False):
                    st.write(result.intake.reasoning)

        # Card 2 — Triage
        with st.expander("Triage Agent — " + (result.triage.urgency.value if result.triage else "NOT RUN"), expanded=True):
            if result.triage:
                col1, col2 = st.columns(2)
                col1.metric("Urgency", result.triage.urgency.value)
                col2.metric("Category", result.triage.category.value)
                st.write(f"**Root Causes:** {' · '.join(result.triage.likely_root_causes)}")
                st.write(f"**Required Skills:** {', '.join(result.triage.recommended_skills)}")
                st.write(f"**Property History:** {result.triage.property_history_summary}")
                with st.expander("Reasoning", expanded=False):
                    st.write(result.triage.reasoning)

        # Card 3 — Inventory
        with st.expander("Inventory Agent — " + ("PROCEED TODAY" if result.inventory and result.inventory.can_proceed_today else "PARTS NEEDED" if result.inventory else "NOT RUN"), expanded=True):
            if result.inventory:
                st.write(f"**Can Proceed Today:** {'✅ Yes' if result.inventory.can_proceed_today else '⚠️ No — parts needed'}")
                if result.inventory.parts_in_stock:
                    st.write("**Parts In Stock:**")
                    for p in result.inventory.parts_in_stock:
                        st.write(f"  • {p.get('name', 'Unknown')} (qty: {p.get('quantity_available', '?')})")
                if result.inventory.parts_needed_to_order:
                    st.write("**Parts To Order:**")
                    for p in result.inventory.parts_needed_to_order:
                        st.write(f"  • {p.get('name', 'Unknown')}")
                with st.expander("Reasoning", expanded=False):
                    st.write(result.inventory.reasoning)

        # Card 4 — Dispatch
        with st.expander("Dispatch Agent — " + (result.dispatch.recommended_vendor_name if result.dispatch else "NOT RUN"), expanded=True):
            if result.dispatch:
                col1, col2 = st.columns(2)
                col1.metric("Vendor", result.dispatch.recommended_vendor_name)
                col2.metric("Estimated Cost", f"${result.dispatch.estimated_cost_usd:.0f}")
                st.write(f"**Scheduled:** {result.dispatch.scheduled_window}")
                st.write(f"**Job Brief (EN):** {result.dispatch.job_brief_en}")
                if result.dispatch.job_brief_translated:
                    st.write(f"**Job Brief ({result.dispatch.translation_language}):** {result.dispatch.job_brief_translated}")
                with st.expander("Reasoning", expanded=False):
                    st.write(result.dispatch.reasoning)

        # Card 5 — Compliance
        with st.expander("Compliance Auditor — " + (result.compliance.decision.value if result.compliance else "NOT RUN"), expanded=True):
            if result.compliance:
                decision = result.compliance.decision.value
                if decision == "APPROVED":
                    st.success(f"**Decision: {decision}**")
                else:
                    st.error(f"**Decision: {decision}**")
                st.write(f"**Rules Checked:** {', '.join(result.compliance.rules_checked)}")
                if result.compliance.violations:
                    for v in result.compliance.violations:
                        st.error(f"Violation: {v}")
                st.write(f"**Recommendation:** {result.compliance.recommendation}")
                with st.expander("Reasoning", expanded=False):
                    st.write(result.compliance.reasoning)

        # --- Section 3: Approval Card ---
        if result.final_status == "READY_FOR_APPROVAL":
            st.divider()
            st.subheader("📋 Property Manager Decision")

            st.markdown(
                f"""
| Field | Value |
|---|---|
| **Tenant** | {result.intake.tenant_name} — Unit {result.intake.unit_id} |
| **Issue** | {result.intake.summary} |
| **Vendor** | {result.dispatch.recommended_vendor_name} · {result.dispatch.scheduled_window} |
| **Estimated Cost** | ${result.dispatch.estimated_cost_usd:.0f} |
| **Compliance** | ✅ APPROVED |
"""
            )

            col1, col2 = st.columns(2)
            if col1.button("✅ APPROVE DISPATCH", type="primary", use_container_width=True):
                st.success("✅ Dispatch approved! Work order created. Carlos M. notified for Today 2-4 PM.")
                st.balloons()
            if col2.button("❌ REJECT", use_container_width=True):
                st.error("Dispatch rejected. Ticket returned for review.")

        # --- Section 4: Audit Trail ---
        st.divider()
        with st.expander("📋 Audit Trail", expanded=False):
            if result.audit_trail:
                for entry in result.audit_trail:
                    st.write(f"• **{entry.get('agent', '?').title()}** — {entry.get('action', '?')} at {entry.get('timestamp', '?')}")
