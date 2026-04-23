# PlatRock Architecture

## Agent Pipeline

Tenant request → Intake Agent → [Triage Agent || Inventory Agent] → Dispatch Agent → Compliance Auditor → Property Manager

## Agent Descriptions

| Agent | Input | Output | Data source |
|---|---|---|---|
| Intake | Raw tenant message | Structured ticket or clarifying question | — |
| Triage | IntakeOutput | Urgency, category, root causes, skills | property_history.json |
| Inventory | TriageOutput | Parts in stock, can proceed today | inventory.json |
| Dispatch | TriageOutput + InventoryOutput | Vendor, schedule, job brief (EN + translated) | vendors.json |
| Compliance Auditor | DispatchOutput + TriageOutput | APPROVED / REJECTED / NEEDS_MANAGER_EXCEPTION | compliance_rules.json |

## Key Design Decisions

- **Pydantic schemas** enforce typed I/O contracts at every agent boundary
- **Parallel execution**: Triage and Inventory run concurrently (designed), sequentially (MVP)
- **Hard veto**: Compliance Auditor cannot be overridden by any other agent
- **Fence-stripping defense**: LLM markdown wrappers stripped in code, not just prompt
- **Prompts centralized**: All system prompts in src/prompts/system_prompts.py
- **Bilingual dispatch**: Dispatch Agent translates job briefs to vendor's preferred language
- **Multi-turn clarification**: Intake Agent asks one clarifying question if info insufficient

## Security Model (Defense-in-Depth)

1. Input validation: 2000-char cap on raw_message enforced by Pydantic
2. Role constraints: tight system prompts, structured output only
3. PII minimization: no persistent tenant data in MVP
4. Human-in-the-loop: agents propose, property manager approves
5. Observability: full reasoning trace + immutable JSONL audit log
