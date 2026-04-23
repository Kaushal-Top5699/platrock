"""
Intake Agent — first point of contact with the tenant.

Converts a raw TenantMessage into a validated IntakeOutput by making a single
LLM call to Claude Sonnet 4.5.  The system prompt lives in
src/prompts/system_prompts.py; this module contains only wiring logic.

Security notes:
- Tenant input travels in the user role only; it is never interpolated into
  the system prompt, preventing cross-role injection.
- The 2 000-char cap on raw_message is enforced upstream by TenantMessage's
  Pydantic field constraint before this function is reached.
- Prompt injection attempts are addressed by the system prompt's explicit
  defense instructions; schema validation then catches any malformed response
  that such an attempt might produce.
- The API key is loaded from the environment only; it is never logged, printed,
  or referenced in source code.
"""

import json
import os

from anthropic import Anthropic
from dotenv import load_dotenv
from pydantic import ValidationError

from src.prompts.system_prompts import INTAKE_SYSTEM_PROMPT
from src.schemas import IntakeOutput, TenantMessage

load_dotenv()

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. "
        "Copy .env.example to .env and fill in your key before running PlatRock."
    )

client = Anthropic()

MODEL_ID = "claude-sonnet-4-5-20250929"


def run_intake_agent(tenant_message: TenantMessage) -> IntakeOutput:
    """
    Run the Intake Agent: convert a tenant's raw maintenance message into
    a structured ticket or a clarifying question.

    Makes ONE LLM call to Claude Sonnet 4.5 with INTAKE_SYSTEM_PROMPT as the
    system prompt and the tenant data as the user message.  The response is
    validated against IntakeOutput before being returned.

    Raises:
        ValueError: if the LLM response is not valid JSON or fails Pydantic
                    validation.  Loud failure is intentional — silent
                    degradation here would corrupt every downstream agent.
    """
    user_content = "Tenant maintenance report:\n" + json.dumps(
        {
            "unit_id": tenant_message.unit_id,
            "tenant_name": tenant_message.tenant_name,
            "raw_message": tenant_message.raw_message,
            "language": tenant_message.language,
        }
    )

    response = client.messages.create(
        model=MODEL_ID,
        max_tokens=1024,
        system=INTAKE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text.strip()
    # Claude occasionally wraps JSON in markdown fences despite explicit instructions.
    # Strip them before parsing so the constraint is enforced in code, not just prompt.
    if raw_text.startswith("```"):
        raw_text = raw_text.split("\n", 1)[-1]  # drop opening fence line
        raw_text = raw_text.rsplit("```", 1)[0].strip()  # drop closing fence

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Intake Agent returned non-JSON response. "
            f"First 200 chars: {raw_text[:200]!r}"
        ) from exc

    try:
        return IntakeOutput(**parsed)
    except ValidationError as exc:
        raise ValueError(
            f"Intake Agent returned invalid structure: {exc}"
        ) from exc
