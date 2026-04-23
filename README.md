# PlatRock

PlatRock is a multi-agent AI system that automates the property maintenance lifecycle. A tenant reports an issue in natural language, and six specialized agents — Intake, Triage, Inventory, Dispatch, Compliance Auditor, and Orchestrator — collaborate to produce a compliant, vendor-matched, inventory-verified dispatch recommendation. The property manager makes the final approval via a Streamlit dashboard; no real-world action is taken without human sign-off.

## Getting Started

**Prerequisites:** Python 3.11+, an Anthropic API key.

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd platrock

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the smoke test to verify the setup
pytest tests/test_smoke.py -v
```

**Before Session 2:** copy `.env.example` to `.env` and fill in your `ANTHROPIC_API_KEY` — LLM calls begin in the next session.

```bash
cp .env.example .env
# then open .env and set: ANTHROPIC_API_KEY=sk-ant-...
```
