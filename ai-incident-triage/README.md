# ai-incident-triage

An AI-powered incident triage system. A LangGraph-orchestrated pipeline of
specialized agents (classification incl. severity, investigation with parallel
log-analysis / runbook / kubernetes sub-agents, RCA + report, notification)
ingests an incident, retrieves relevant knowledge via RAG, reasons over
evidence, and produces a structured, explainable triage report — with human
approval and verification steps built into the graph.

## Setup

```bash
uv sync
```

## Run tests

```bash
uv run pytest
```

## Run the triage pipeline

### CLI

Run an incident JSON file through the LangGraph pipeline (deterministic
rule-based agents, no API key needed):

```bash
uv run python -m app.main data/incidents/database_timeout.json --auto-approve
```

- Any file in `data/incidents/` works as the argument.
- Add `--use-llm` to use the LLM-backed classification/RCA agents (requires a
  provider API key in `.env`).
- Use `--require-approval` instead of `--auto-approve` to make P1/P2 or
  low-confidence incidents require human sign-off (they will be rejected
  without a reviewer).

### UI

```bash
uv run streamlit run app/ui/streamlit_app.py
```

Then open the displayed local URL, pick a sample incident (or paste your own
JSON), and click **Run Triage**. The UI calls the same graph as the CLI —
`app.graph.workflow.triage_graph` — as the single orchestration entry point.

### Graph diagram

Regenerate the workflow visualization at `docs/triage_graph.png`:

```bash
uv run python scripts/generate_graph_png.py
```
