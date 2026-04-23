# PlatRock — Multi-Agent Property Management System

## Current Status

**Complete:** Scaffolding Phases 1.A through 1.D — folder structure (`src/`, `src/agents/`, `src/prompts/`, `data/`, `tests/`, `docs/`), Python venv with 7 dependencies installed, smoke test passing, and 4 seeded JSON data files supporting the Maria/Carlos AC demo scenario. Phase 2.A (`src/schemas.py`) — 4 enums, 8 I/O schema groups, 16 Pydantic classes total, with 26 passing pytest tests covering all security constraints: `max_length=2000`, `min_length=1`, `ge=0`, and the full `NEEDS_CLARIFICATION` branch. Phase 2.B (`src/prompts/system_prompts.py`) — `INTAKE_SYSTEM_PROMPT`, 6316 chars / 135 lines, with JSON-first constraint, two worked examples, prompt injection defense with concrete example phrases, and structured reasoning field guidance. Phase 2.C (`src/agents/intake.py` — 83 lines, `run_intake_agent()` makes live Claude Sonnet 4.5 API calls, Pydantic-validates `IntakeOutput`, includes fence-stripping defense). Phase 2.D (`tests/test_intake_live.py` — 2 live LLM tests, 28/28 total suite passing). Session 4: All 5 agents built and tested (`triage.py`, `inventory.py`, `dispatch.py`, `compliance.py`, `orchestrator.py`). LangGraph orchestration wiring all agents into a sequential pipeline. Full Maria/Carlos AC demo scenario passes end-to-end: TICKET_READY → HIGH/MODERATE HVAC → parts in stock → Carlos M. dispatched → APPROVED → READY_FOR_APPROVAL. 33/33 tests passing.

**In Progress:** None — Session 4 is a clean stopping point.

**Next:** Session 5 — Streamlit UI (`streamlit_app.py`): chat panel for tenant message input, live agent activity dashboard showing each agent's output, approval card with APPROVE/REJECT buttons, audit trail viewer.

**Key Versions:** Python 3.13.3 · anthropic 0.96.0 · langgraph 1.1.9 · langchain-anthropic 1.4.1 · streamlit 1.56.0 · pydantic 2.13.3

## Project Context

This project is a submission for the **Wipro Junior FDE Pre-screening Assignment** (Design and Implementation of a Multi-Agent System). Deadline: Thursday April 23, 2026, 11:59 PM CST. Presentation: Friday April 24, 2026, 10:00 AM CST, Wipro Plano office.

Built by Kaushal, in consultation with Starcore Capital — a DFW real estate firm that is actively building its property management arm. The problem space comes from real operator pain points: property managers are overwhelmed by "maintenance noise" — the endless loop of reporting, triaging, vendor chasing, and inventory tracking.

## Project Overview

PlatRock is a multi-agent AI system that automates the property maintenance lifecycle. A tenant reports an issue in natural language, and six specialized agents collaborate to produce a compliant, vendor-matched, inventory-verified dispatch recommendation — with a human property manager making the final approval.

**Origin story:** The founder originally built PlatN, a consumer service marketplace, three years ago. It worked but was clunky — too many forms, too many phone calls. Agentic AI finally makes the original vision possible, and PlatRock is the enterprise B2B evolution for property management.

## The Six Agents

1. **Intake Agent** — Conversational interface with the tenant. Asks at most one clarifying question. Produces a structured ticket.

2. **Triage Agent** — Scores urgency (EMERGENCY / HIGH / MODERATE / LOW), classifies the issue, checks property history, and proposes required skill + estimated parts.

3. **Inventory Agent** — Checks simulated inventory for the parts Triage estimated. Either confirms stock (`NO_PURCHASE_REQUIRED`) or stubs a purchase (`PURCHASE_STUBBED`).

4. **Dispatch Agent** — Matches a vendor by skill, location, rating, and availability. Translates the job brief to the vendor's preferred language. Proposes cost estimate and scheduling window.

5. **Compliance Auditor** — Checks the proposed dispatch against a rules file (certification, cost ceiling, Fair Housing, audit completeness). **Has hard veto power.** Cannot be overridden by other agents.

6. **Orchestrator** — Coordinates the other five. Holds shared state. Handles human-in-the-loop approval from the property manager. Logs everything.

## Agent Flow
Tenant → Orchestrator → Intake → (Triage || Inventory in parallel) → Dispatch → Compliance Auditor → Orchestrator → Property Manager UI → [if approved: notifications + audit log]

Triage and Inventory run in parallel (neither needs the other's output). All other steps are sequential.

## Demo Scenario (for Friday presentation)

**Maria, a tenant in apartment C-204 of a DFW apartment complex, reports her AC is blowing warm air.** The agents collaborate to:
- Ask one clarifying question (water leak? unusual sounds?)
- Classify as MODERATE urgency HVAC cooling failure
- Check property history (filter was replaced 6 months ago — probably refrigerant/compressor issue)
- Verify refrigerant and compressor capacitor are in inventory
- Match Carlos M., an EPA-608-certified HVAC technician with 4.8⭐ rating, Spanish-preferred, available 2-4 PM today
- Translate job brief into Spanish for Carlos
- Pass all compliance checks (cost under $500 threshold, vendor certified, Fair Housing compliant)
- Surface a single-click APPROVE/REJECT card to the property manager

End-to-end flow target: under 3 minutes.

## Tech Stack

| Layer | Choice |
|---|---|
| Language | Python 3.11+ |
| Agent framework | LangGraph |
| LLM | Claude Sonnet 4.5 via Anthropic API |
| UI | Streamlit |
| Data | JSON files (vendors, inventory, property_history, compliance_rules) |
| Deployment | Streamlit Community Cloud (free tier) |
| Version control | Public GitHub repo |
| Testing | Single end-to-end integration test |

## Project Structure
platrock/
├── PROJECT.md
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── streamlit_app.py
├── src/
│   ├── init.py
│   ├── orchestrator.py            ← LangGraph workflow
│   ├── agents/
│   │   ├── init.py
│   │   ├── intake.py
│   │   ├── triage.py
│   │   ├── inventory.py
│   │   ├── dispatch.py
│   │   └── compliance_auditor.py
│   ├── prompts/
│   │   └── system_prompts.py
│   ├── schemas.py                 ← Pydantic models for all agent I/O
│   └── utils.py
├── data/
│   ├── vendors.json
│   ├── inventory.json
│   ├── property_history.json
│   └── compliance_rules.json
├── tests/
│   └── test_e2e_ac_scenario.py
└── docs/
├── architecture_diagram.png
└── report.md

## Agent I/O Contracts

All agents communicate via strict Pydantic schemas defined in `src/schemas.py`. Each agent:
- Receives typed input
- Returns typed output matching its contract
- Never emits free-form text to downstream agents

This is a security feature (see Guardrails below).

## Security & Guardrails (Defense-in-Depth)

Five layers:

1. **Input validation & prompt injection defense** — Sanitization layer on tenant input. Character limits (2000 char cap). Downstream agents never see raw tenant text — only structured ticket fields.

2. **LLM role constraints** — Each agent has a tightly scoped system prompt. Structured output via Pydantic schemas. Agents that violate their role return `ROLE_VIOLATION`.

3. **Data handling** — PII minimization (unit number internally, full name only for manager display). API keys in environment variables, never in code. No persistent tenant data in MVP (in-memory only).

4. **Human-in-the-loop** — Agents propose, humans dispose. No real-world action (dispatch, notifications, invoicing) without property manager approval. Compliance Auditor has hard veto — cannot be overridden by other agents or the Orchestrator.

5. **Observability** — Full agent trace logged to `audit_log.jsonl`. Each agent produces a `reasoning` field. Dashboard shows live agent state. Append-only immutable audit log.

## Explicit MVP Scope

**BUILT (in code):**
- All 6 agents with LLM-powered decision logic
- LangGraph orchestration with parallel Triage + Inventory
- Streamlit UI with chat + live agent dashboard + manager approval view
- Structured output enforcement via Pydantic
- Basic input sanitization
- Compliance Auditor veto logic
- Audit log (JSONL)
- One canned AC demo scenario working end-to-end
- Deployment to Streamlit Cloud with public URL

**DESCRIBED IN REPORT (designed, deferred):**
- Advanced input sanitization beyond basic patterns
- PII redaction from audit logs
- Cryptographic signing of audit log
- Second agent tier: Risk Predictor, Customer Communicator
- Real supplier API integration (MVP uses stub)
- Real vendor directory with live availability (MVP uses JSON)
- Real notification dispatch (MVP displays "would send" messages)
- Persistent DB with row-level access control
- Full unit test coverage

## Development Conventions

- **Work in small phases.** Each Claude Code session should tackle one focused phase, verify it works, and stop.
- **Pydantic schemas first.** Before writing an agent, define its input/output schema.
- **Prompts live in `src/prompts/system_prompts.py`.** Never hardcode prompts inside agent logic.
- **All agents are async.** This enables parallel execution where appropriate.
- **No secrets in code.** Use `.env` locally, Streamlit secrets in production.
- **Commit frequently with clear messages.** The public GitHub repo will be reviewed.
- **Every agent produces a `reasoning` field** explaining its decision.

## Timeline

- **Tuesday April 21 (today):** Scaffold + first agent (Intake) end-to-end + Orchestrator spine.
- **Tuesday evening:** Add Triage and Inventory agents.
- **Wednesday April 22:** Add Dispatch + Compliance Auditor + Streamlit UI + full end-to-end wiring.
- **Thursday April 23 morning:** Deploy to Streamlit Cloud, polish UI, write architecture diagram.
- **Thursday April 23 afternoon:** Write 1-2 page report, record backup demo video, prepare presentation slides.
- **Thursday April 23, 11:59 PM CST:** Submit GitHub link via email.
- **Friday April 24, 10:00 AM CST:** Present in-person at Wipro Plano office.

## Important Reminders for Claude Code

- **Ask before scaffolding.** Before running package install or destructive commands, confirm with the user.
- **Respect the MVP scope.** If something falls in the "described in report" bucket, don't build it — note it for the report instead.
- **This is a presentation-driven project.** Code quality and architectural clarity matter as much as function. Interviewers will read the repo.
- **Security is a first-class concern.** Do not weaken the guardrails for convenience.
- **Explain decisions as you work.** The user is learning the LangGraph patterns as we build.
- **Stop after each phase** and wait for user confirmation before moving on.