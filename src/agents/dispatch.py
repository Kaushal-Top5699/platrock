"""
Dispatch Agent — vendor selection, scheduling, and bilingual job brief.

Receives a validated TriageOutput, InventoryOutput, and the raw vendor list
loaded from data/vendors.json. Returns a validated DispatchOutput containing
the recommended vendor, scheduled window, English job brief, translated job
brief (when the vendor's preferred language is not English), and cost estimate.

The orchestrator is responsible for loading data/vendors.json and passing the
full list — this agent only performs the matching and translation logic via a
single LLM call.

Security notes:
- Only structured triage and inventory fields reach this agent — raw tenant
  text has been discarded after the Intake Agent validated it.
- The cost estimate is surfaced for human review; no financial transaction
  occurs without property manager approval.
- API key is loaded from the environment only; never logged or referenced in code.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from src.prompts.system_prompts import DISPATCH_SYSTEM_PROMPT
from src.schemas import DispatchOutput, InventoryOutput, TriageOutput

load_dotenv()

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Copy .env.example to .env and fill in your key before running PlatRock."
    )

client = Anthropic()

MODEL_ID = "claude-sonnet-4-5-20250929"


def run_dispatch_agent(
    triage_output: TriageOutput,
    inventory_output: InventoryOutput,
    vendors: list[dict],
) -> DispatchOutput:
    """
    Run the Dispatch Agent: select a vendor, schedule the job, write a job
    brief in English, and translate it if the vendor speaks another language.

    Makes ONE LLM call to Claude Sonnet 4.5 with DISPATCH_SYSTEM_PROMPT as the
    system prompt and the combined triage + inventory + vendor data as the user
    message. The response is validated against DispatchOutput before returning.

    Args:
        triage_output:    Validated output from the Triage Agent.
        inventory_output: Validated output from the Inventory Agent.
        vendors:          Full vendor list from data/vendors.json, loaded by
                          the orchestrator.

    Raises:
        ValueError: if the LLM response is not valid JSON or fails Pydantic
                    validation. Loud failure is intentional — a corrupt
                    DispatchOutput would give the Compliance Auditor wrong data.
    """
    user_content = "Dispatch request:\n" + json.dumps(
        {
            "ticket_id": triage_output.ticket_id,
            "category": triage_output.category.value,
            "recommended_skills": triage_output.recommended_skills,
            "can_proceed_today": inventory_output.can_proceed_today,
            "parts_in_stock": inventory_output.parts_in_stock,
            "vendors": vendors,
        }
    )

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=DISPATCH_SYSTEM_PROMPT,
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
            f"Dispatch Agent returned non-JSON response. "
            f"First 200 chars: {raw_text[:200]!r}"
        ) from exc

    try:
        return DispatchOutput(**parsed)
    except ValidationError as exc:
        raise ValueError(
            f"Dispatch Agent returned invalid structure: {exc}"
        ) from exc
