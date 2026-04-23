"""
Triage Agent — urgency scoring and issue classification.

Receives a completed IntakeOutput plus pre-filtered property history for the
relevant unit, and returns a validated TriageOutput.  The orchestrator is
responsible for loading data/property_history.json and filtering to unit_id
before calling this function.

Security notes:
- Downstream agents never receive raw_message directly; the Triage Agent only
  passes ticket fields that were already validated by the Intake Agent.
- Prompt injection defense is layered: the system prompt instructs the model to
  ignore embedded instructions, and Pydantic schema validation catches any
  malformed response such an attempt might produce.
- API key is loaded from the environment only; never logged or referenced in code.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from src.prompts.system_prompts import TRIAGE_SYSTEM_PROMPT
from src.schemas import IntakeOutput, TriageOutput

load_dotenv()

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Copy .env.example to .env and fill in your key before running PlatRock."
    )

client = Anthropic()

MODEL_ID = "claude-sonnet-4-5-20250929"


def run_triage_agent(
    intake_output: IntakeOutput,
    property_history: list[dict],
) -> TriageOutput:
    """
    Run the Triage Agent: score urgency, classify the issue, and recommend
    vendor skills based on the intake ticket and unit property history.

    Makes ONE LLM call to Claude Sonnet 4.5 with TRIAGE_SYSTEM_PROMPT as the
    system prompt and the structured ticket + history as the user message.
    The response is validated against TriageOutput before being returned.

    Args:
        intake_output: Validated output from the Intake Agent (TICKET_READY).
        property_history: Pre-filtered list of prior work-order dicts for the
                          relevant unit_id, loaded by the orchestrator from
                          data/property_history.json.

    Raises:
        ValueError: if the LLM response is not valid JSON or fails Pydantic
                    validation.  Loud failure is intentional — a corrupt
                    TriageOutput would propagate incorrect urgency downstream.
    """
    user_content = "Intake ticket for triage:\n" + json.dumps(
        {
            "ticket_id": intake_output.ticket_id,
            "unit_id": intake_output.unit_id,
            "summary": intake_output.summary,
            "raw_message": intake_output.raw_message,
            "property_history": property_history,
        }
    )

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=TRIAGE_SYSTEM_PROMPT,
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
            f"Triage Agent returned non-JSON response. "
            f"First 200 chars: {raw_text[:200]!r}"
        ) from exc

    try:
        return TriageOutput(**parsed)
    except ValidationError as exc:
        raise ValueError(
            f"Triage Agent returned invalid structure: {exc}"
        ) from exc
