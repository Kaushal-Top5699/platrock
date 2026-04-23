# PlatRock — Technical Report
**Candidate:** Kaushal Topinkatti  
**Assignment:** Junior FDE Pre-Screening  
**Submitted:** April 23, 2026  
**GitHub:** https://github.com/Kaushal-Top5699/platrock  
**Live Demo:** https://platrock.streamlit.app

---

## Problem Statement

Property management companies lose significant time to maintenance coordination — triaging tenant requests, finding certified vendors, checking parts availability, and ensuring compliance before dispatching. The process is manual, error-prone, and often delayed. PlatRock automates this lifecycle using a multi-agent AI system.

## Solution Overview

PlatRock is a 5-agent LangGraph pipeline that takes a tenant's natural language maintenance request and produces a compliance-verified, vendor-matched dispatch recommendation for a property manager to approve or reject in one click.

**Demo scenario:** Maria Rodriguez (Unit C-204) reports her AC is blowing warm air. Within ~45 seconds, PlatRock:
1. Creates a structured ticket with urgency classification
2. Checks property history (filter replaced Oct 2025 — likely refrigerant/capacitor issue)
3. Confirms R410A refrigerant and compressor capacitor are in stock
4. Selects Carlos M. (EPA-608, NATE certified, 4.8★, Spanish-preferred) for Today 2-4 PM
5. Generates a bilingual job brief (English + Spanish)
6. Passes all 5 compliance rules
7. Presents property manager with a single APPROVE/REJECT card

## Architecture

**Stack:** Python 3.13 · LangGraph 1.1.9 · Claude Sonnet 4.5 (claude-sonnet-4-5-20250929) · Pydantic 2.13 · Streamlit 1.56

**Agent pipeline:**
Intake → (Triage ∥ Inventory) → Dispatch → Compliance Auditor → Property Manager UI

Each agent receives a typed Pydantic input, calls Claude Sonnet 4.5 with a carefully engineered system prompt, and returns a validated Pydantic output. The Orchestrator (LangGraph StateGraph) coordinates the pipeline and maintains a full audit trail.

**Key design decisions:**
- Pydantic schemas enforce I/O contracts at every agent boundary — no silent failures
- All system prompts centralized in src/prompts/system_prompts.py — never hardcoded
- Fence-stripping defense in agent code handles LLM markdown wrapper habit
- Multi-turn clarification: Intake asks exactly one clarifying question if info is insufficient
- Compliance Auditor has hard veto power — cannot be overridden

## Security Model

Five layers of defense-in-depth:

1. **Input validation** — 2000-character cap on raw_message enforced by Pydantic schema
2. **Role constraints** — tight system prompts with explicit prompt injection defense patterns
3. **Data handling** — API key in environment only, never in source; no persistent tenant PII
4. **Human-in-the-loop** — agents propose, property manager approves; no autonomous dispatch
5. **Observability** — every agent produces a reasoning field; immutable JSONL audit trail

## Testing

33 tests across 6 files:
- 1 smoke test (import chain verification)
- 25 schema contract tests (all Pydantic constraints verified: max_length, min_length, ge=0)
- 5 live LLM integration tests (real Claude Sonnet 4.5 API calls)
- 1 end-to-end orchestration test (full Maria scenario: 5 agents, READY_FOR_APPROVAL)

All 33 tests pass. Live tests are skipped in CI if ANTHROPIC_API_KEY is absent.

## Mock Data Strategy

JSON files serve as the data layer for the MVP (vendors, inventory, property history, compliance rules). This was an intentional architectural choice — the agent code is data-source agnostic. In production, each file maps 1:1 to a live integration:

| Mock file | Production integration |
|---|---|
| vendors.json | ServiceChannel or equivalent contractor management platform |
| inventory.json | Yardi, AppFolio, or warehouse management system |
| property_history.json | Property management database |
| compliance_rules.json | Rules engine (Drools, Camunda) or legal/HR system |

## What I Would Build Next

1. **Risk Predictor agent** — predicts recurring issues based on property history patterns
2. **Persistent database** — replace JSON with PostgreSQL + SQLAlchemy
3. **Real vendor integrations** — ServiceChannel API for live availability
4. **Async parallel execution** — LangGraph fan-out for true Triage ∥ Inventory parallelism
5. **Tenant portal** — separate UI for tenants to submit and track requests

## Acknowledgements

System designed in consultation with Starcore Capital (DFW real estate), whose property management team confirmed the core pain points: maintenance noise, vendor qualification, and compliance overhead.

---
