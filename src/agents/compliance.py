"""
Compliance Auditor — final gate before any dispatch is approved.

Receives the proposed DispatchOutput, the TriageOutput (for urgency), the
matched vendor's certifications, and the full compliance rules list loaded
from data/compliance_rules.json. Returns a validated ComplianceOutput.

The Compliance Auditor has hard veto power. A REJECTED decision cannot be
overridden by the Orchestrator or any other agent — it surfaces directly to
the property manager with violation details.

The orchestrator is responsible for loading data/compliance_rules.json and
resolving the dispatched vendor's certifications from data/vendors.json before
calling this function.

Security notes:
- Only structured fields from prior agents reach this auditor — raw tenant
  text has been discarded long before this point in the pipeline.
- The veto is enforced here (Pydantic) and again in the Orchestrator, which
  checks compliance.decision before enabling the manager approval UI.
- API key is loaded from the environment only; never logged or referenced in code.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from src.prompts.system_prompts import COMPLIANCE_SYSTEM_PROMPT
from src.schemas import ComplianceOutput, DispatchOutput, TriageOutput

load_dotenv()

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Copy .env.example to .env and fill in your key before running PlatRock."
    )

client = Anthropic()

MODEL_ID = "claude-sonnet-4-5-20250929"


def run_compliance_agent(
    dispatch_output: DispatchOutput,
    triage_output: TriageOutput,
    vendor_certifications: list[str],
    compliance_rules: list[dict],
) -> ComplianceOutput:
    """
    Run the Compliance Auditor: evaluate the proposed dispatch against every
    compliance rule and return an APPROVED, REJECTED, or NEEDS_MANAGER_EXCEPTION
    verdict.

    Makes ONE LLM call to Claude Sonnet 4.5 with COMPLIANCE_SYSTEM_PROMPT as
    the system prompt and the combined dispatch + triage + rules data as the
    user message. The response is validated against ComplianceOutput before
    being returned.

    Args:
        dispatch_output:       Validated output from the Dispatch Agent.
        triage_output:         Validated output from the Triage Agent (provides urgency).
        vendor_certifications: Certifications held by the recommended vendor,
                               resolved from data/vendors.json by the orchestrator.
        compliance_rules:      Rules list from data/compliance_rules.json,
                               loaded by the orchestrator.

    Raises:
        ValueError: if the LLM response is not valid JSON or fails Pydantic
                    validation. Loud failure is intentional — a silent failure
                    here would allow an unchecked dispatch to reach the manager.
    """
    user_content = "Dispatch proposal for compliance review:\n" + json.dumps(
        {
            "ticket_id": dispatch_output.ticket_id,
            "urgency": triage_output.urgency.value,
            "estimated_cost_usd": dispatch_output.estimated_cost_usd,
            "vendor_certifications": vendor_certifications,
            "required_skills": triage_output.recommended_skills,
            "compliance_rules": compliance_rules,
        }
    )

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=COMPLIANCE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text.strip()
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]
        raw_text = raw_text.rsplit("```", 1)[0].strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Compliance Auditor returned non-JSON response. "
            f"First 200 chars: {raw_text[:200]!r}"
        ) from exc

    try:
        return ComplianceOutput(**parsed)
    except ValidationError as exc:
        raise ValueError(
            f"Compliance Auditor returned invalid structure: {exc}"
        ) from exc
