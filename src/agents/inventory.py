"""
Inventory Agent — parts availability check for a proposed repair.

Receives a validated TriageOutput plus the full inventory list loaded from
data/inventory.json, and returns a validated InventoryOutput.  The orchestrator
is responsible for loading the inventory file; this agent only performs the
matching logic via a single LLM call.

Runs in parallel with any property-history lookups — neither this agent nor the
Triage Agent depends on the other's output.

Security notes:
- The agent receives only structured triage fields (category, root causes,
  skills) — raw tenant text never reaches this agent.
- Prompt injection defense is layered: the system prompt instructs the model to
  ignore embedded instructions, and Pydantic validation catches malformed output.
- API key is loaded from the environment only; never logged or referenced in code.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from src.prompts.system_prompts import INVENTORY_SYSTEM_PROMPT
from src.schemas import InventoryOutput, TriageOutput

load_dotenv()

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Copy .env.example to .env and fill in your key before running PlatRock."
    )

client = Anthropic()

MODEL_ID = "claude-sonnet-4-5-20250929"


def run_inventory_agent(
    triage_output: TriageOutput,
    inventory: list[dict],
) -> InventoryOutput:
    """
    Run the Inventory Agent: match triage root causes against on-site inventory
    and determine whether the job can proceed today.

    Makes ONE LLM call to Claude Sonnet 4.5 with INVENTORY_SYSTEM_PROMPT as the
    system prompt and the triage data + inventory snapshot as the user message.
    The response is validated against InventoryOutput before being returned.

    Args:
        triage_output: Validated output from the Triage Agent.
        inventory: Full inventory list loaded from data/inventory.json by the
                   orchestrator.

    Raises:
        ValueError: if the LLM response is not valid JSON or fails Pydantic
                    validation.  Loud failure is intentional — a corrupt
                    InventoryOutput would give the Dispatch Agent incorrect
                    parts availability information.
    """
    user_content = "Triage assessment for inventory check:\n" + json.dumps(
        {
            "ticket_id": triage_output.ticket_id,
            "category": triage_output.category.value,
            "likely_root_causes": triage_output.likely_root_causes,
            "recommended_skills": triage_output.recommended_skills,
            "inventory": inventory,
        }
    )

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=INVENTORY_SYSTEM_PROMPT,
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
            f"Inventory Agent returned non-JSON response. "
            f"First 200 chars: {raw_text[:200]!r}"
        ) from exc

    try:
        return InventoryOutput(**parsed)
    except ValidationError as exc:
        raise ValueError(
            f"Inventory Agent returned invalid structure: {exc}"
        ) from exc
