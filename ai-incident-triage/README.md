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
