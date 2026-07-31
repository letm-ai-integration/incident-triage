AI Incident Triage Architecture
                         
                         
                         ┌──────────────────────────────┐
                         │       1. INCIDENT INPUT       │
                         │                              │
                         │  Mock Logs / Alerts / Events │
                         │  Metrics / Deployment Data   │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   2. INCIDENT INGESTION      │
                         │                              │
                         │ Normalize                    │
                         │ Deduplicate                  │
                         │ Correlate                    │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │   3. INCIDENT CLASSIFIER     │
                         │                              │
                         │ Kubernetes / Application     │
                         │ Database / Network / IAM     │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │    4. IMPACT ASSESSMENT      │
                         │                              │
                         │ Environment / Service       │
                         │ Users / Business Impact      │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      5. SEVERITY ENGINE      │
                         │                              │
                         │       Rules + LLM            │
                         │          P1 / P2 / P3         │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                  ┌────────────────────────────────────────────┐
                  │         6. INVESTIGATION AGENT             │
                  │                                            │
                  │ Analyze Mock Evidence                      │
                  │ Identify Symptoms                          │
                  │ Generate Possible Hypotheses               │
                  │ Identify Missing Evidence                  │
                  └─────────────────────┬──────────────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │        7. RCA AGENT          │
                         │                              │
                         │ Evidence + Hypotheses       │
                         │ Root Cause + Confidence     │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │       8. KNOWLEDGE BASE      │
                         │                              │
                         │ Runbooks / SOPs              │
                         │ Past Incidents / Postmortems│
                         │              RAG             │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │    9. RESOLUTION PLANNER     │
                         │                              │
                         │ Recommended Actions          │
                         │ Runbook / Troubleshooting    │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │     10. SAFETY + APPROVAL    │
                         │                              │
                         │ Risk Check                   │
                         │ Human Approval               │
                         └──────────────┬───────────────┘
                                        │
                                        ▼
                         ┌──────────────────────────────┐
                         │      11. VERIFICATION        │
                         │                              │
                         │ Based on Mock Outcome Data   │
                         │ Is Incident Resolved?        │
                         └──────────────┬───────────────┘
                                        │
                              ┌─────────┴─────────┐
                              │                   │
                              ▼                   ▼
                         ┌──────────┐       ┌─────────────┐
                         │ RESOLVED │       │ NOT RESOLVED│
                         └────┬─────┘       └──────┬──────┘
                              │                     │
                              │                     │
                              │              ┌──────┘
                              │              │
                              │              ▼
                              │       Investigation Agent
                              │          (Re-investigate)
                              │
                              ▼
                   ┌──────────────────────────────┐
                   │    12. INCIDENT REPORT       │
                   │                              │
                   │ Summary / Severity / Impact  │
                   │ RCA / Confidence / Actions   │
                   │ Team / Status               │
                   └──────────────┬───────────────┘
                                  │
                                  ▼
                   ┌──────────────────────────────┐
                   │    13. NOTIFICATION / TICKET │
                   │                              │
                   │ Jira / Slack / Teams         │
                   │ ServiceNow                   │
                   └──────────────────────────────┘
