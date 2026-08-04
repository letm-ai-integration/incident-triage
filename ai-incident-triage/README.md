# ai-incident-triage

An AI-powered incident triage system. A LangGraph-orchestrated pipeline of
specialized agents (classification, impact, severity, investigation, root-cause
analysis, resolution, reporting, notification) ingests an incident, retrieves
relevant knowledge via RAG, reasons over evidence, and produces a structured,
explainable triage report — with human approval and verification steps built
into the graph.

## Setup

```bash
uv sync
```

## Run tests

```bash
uv run pytest
```
