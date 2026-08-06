**Updated Folder Structure**


# AI Incident Triage - Project Structure

```text
ai-incident-triage/
│
├── app/
│   │
│   ├── main.py
│   ├── config.py
│   ├── dependencies.py
│   │
│   ├── graph/
│   │   ├── workflow.py
│   │   ├── state.py
│   │   ├── router.py
│   │   ├── builder.py
│   │   └── nodes/
│   │       ├── ingestion.py
│   │       ├── classification.py
│   │       ├── investigation.py
│   │       ├── investigation_summary.py
│   │       ├── rca_report.py
│   │       ├── approval.py
│   │       ├── verification.py
│   │       └── notification.py
│   │
│   ├── agents/
│   │   ├── base.py
│   │   │
│   │   ├── classification/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── investigation/
│   │   │   ├── orchestrator.py
│   │   │   ├── prompt.py
│   │   │   ├── parser.py
│   │   │   │
│   │   │   ├── log_analysis/
│   │   │   │   ├── agent.py
│   │   │   │   ├── prompt.py
│   │   │   │   └── parser.py
│   │   │   │
│   │   │   ├── runbook/
│   │   │   │   ├── agent.py
│   │   │   │   ├── prompt.py
│   │   │   │   └── parser.py
│   │   │   │
│   │   │   └── kubernetes/
│   │   │       ├── agent.py
│   │   │       ├── prompt.py
│   │   │       └── parser.py
│   │   │
│   │   ├── rca_report/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   └── notification/
│   │       ├── agent.py
│   │       └── prompt.py
│   │
│   ├── domain/
│   │   ├── models/
│   │   │   ├── incident.py
│   │   │   ├── classification.py
│   │   │   ├── evidence.py
│   │   │   ├── hypothesis.py
│   │   │   ├── root_cause.py
│   │   │   ├── approval.py
│   │   │   ├── verification.py
│   │   │   └── report.py
│   │   │
│   │   ├── enums/
│   │   │   ├── priority.py
│   │   │   ├── incident_type.py
│   │   │   ├── environment.py
│   │   │   ├── team.py
│   │   │   └── status.py
│   │   │
│   │   └── constants.py
│   │
│   ├── services/
│   │   ├── ingestion_service.py
│   │   ├── correlation_service.py
│   │   ├── classification_service.py
│   │   ├── investigation_service.py
│   │   ├── evidence_service.py
│   │   ├── hypothesis_service.py
│   │   ├── rca_report_service.py
│   │   ├── approval_service.py
│   │   ├── verification_service.py
│   │   └── notification_service.py
│   │
│   ├── knowledge/
│   │   ├── embeddings.py
│   │   ├── vector_store.py
│   │   ├── retriever.py
│   │   ├── loader.py
│   │   └── chunker.py
│   │
│   ├── llm/
│   │   ├── factory.py
│   │   ├── providers/
│   │   │   ├── groq.py
│   │   │   ├── openai.py
│   │   │   ├── anthropic.py
│   │   │   └── gemini.py
│   │   └── structured_output.py
│   │
│   ├── prompts/
│   │   ├── shared/
│   │   │   ├── system_prompt.txt
│   │   │   ├── output_format.txt
│   │   │   └── guardrails.txt
│   │   │
│   │   └── templates/
│   │       ├── classification.txt
│   │       ├── investigation.txt
│   │       ├── log_analysis.txt
│   │       ├── runbook.txt
│   │       ├── kubernetes.txt
│   │       ├── rca_report.txt
│   │       └── notification.txt
│   │
│   ├── tools/
│   │   ├── base.py
│   │   │
│   │   ├── mock/
│   │   │   ├── logs.py
│   │   │   ├── metrics.py
│   │   │   ├── deployments.py
│   │   │   ├── events.py
│   │   │   └── alerts.py
│   │   │
│   │   └── adapters/
│   │       ├── kubernetes.py
│   │       ├── prometheus.py
│   │       ├── cloudwatch.py
│   │       ├── jira.py
│   │       ├── slack.py
│   │       └── servicenow.py
│   │
│   ├── rules/
│   │   ├── classification.py
│   │   ├── ownership.py
│   │   └── confidence.py
│   │
│   ├── guardrails/
│   │   ├── domain_guard.py
│   │   ├── pii_guard.py
│   │   ├── safety_guard.py
│   │   ├── prompt_injection.py
│   │   └── validator.py
│   │
│   ├── repositories/
│   │   ├── incident_repository.py
│   │   ├── knowledge_repository.py
│   │   └── report_repository.py
│   │
│   ├── schemas/
│   │   ├── requests.py
│   │   ├── responses.py
│   │   ├── graph_state.py
│   │   └── tool_outputs.py
│   │
│   ├── utils/
│   │   ├── logger.py
│   │   ├── json_utils.py
│   │   ├── time_utils.py
│   │   ├── confidence.py
│   │   └── helpers.py
│   │
│   └── telemetry/
│       ├── langsmith.py
│       ├── tracing.py
│       └── metrics.py
│
├── knowledge_base/
│   ├── runbooks/
│   ├── sop/
│   ├── postmortems/
│   ├── incidents/
│   └── kubernetes/
│
├── data/
│   ├── incidents/
│   │   ├── crashloopbackoff.json
│   │   ├── imagepullbackoff.json
│   │   ├── http503.json
│   │   └── database_timeout.json
│   │
│   ├── outcomes/
│   │   ├── resolved/
│   │   └── unresolved/
│   │
│   └── reports/
│
├── scripts/
│   ├── ingest_knowledge.py
│   ├── build_vector_store.py
│   └── seed_mock_data.py
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── requirements.txt
├── README.md
└── LICENSE
```


**Flow**


                                    +---------------------------+
                                    | Incident Input            |
                                    | Logs / Events / Alerts    |
                                    | Metrics (Optional)        |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | Incident Ingestion        |
                                    | Parse • Normalize         |
                                    | Deduplicate • Correlate   |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | Classification Agent      |
                                    | • Incident Category       |
                                    | • Severity (P1/P2/P3)     |
                                    | (Rules + LLM)             |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | Investigation Agent       |
                                    | Orchestrates Parallel     |
                                    | Investigation Agents      |
                                    +------------+--------------+
                                                 |
                   +-----------------------------+-----------------------------+
                   |                             |                             |
                   v                             v                             v
      +-----------------------+    +-----------------------+    +-----------------------+
      | Log Analysis Agent    |    | Runbook Agent         |    | Kubernetes Agent      |
      | Analyze Mock Logs     |    | RAG Lookup            |    | Analyze Mock K8s Data |
      | Identify Errors       |    | SOPs & Past Incidents |    | Events & Resources    |
      +-----------+-----------+    +-----------+-----------+    +-----------+-----------+
                   \                          |                          /
                    \                         |                         /
                     \________________________|________________________/
                                              |
                                              v
                                    +---------------------------+
                                    | Investigation Summary     |
                                    | Consolidate Findings      |
                                    | Evidence & Hypotheses     |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | RCA & Report Agent        |
                                    | • Root Cause Analysis     |
                                    | • Confidence Score        |
                                    | • Incident Report         |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | Verification              |
                                    | Compare with Mock Outcome |
                                    | Is Incident Resolved?     |
                                    +------------+--------------+
                                                 |
                              +------------------+------------------+
                              |                                     |
                              v                                     v
                  +----------------------+              +----------------------+
                  | Resolved             |              | Not Resolved         |
                  | Generate Final Report|              | Re-investigate       |
                  +----------+-----------+              +----------+-----------+
                             |                                     |
                             |                                     |
                             |                                     |
                             |                          Back to Investigation
                             |                                     ▲
                             +-------------------------------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | Human Review / Approval   |
                                    | Validate AI Findings      |
                                    +------------+--------------+
                                                 |
                                                 v
                                    +---------------------------+
                                    | Notifications             |
                                    | Slack • Jira • Teams      |
                                    +---------------------------+
