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






  Absolutely. Based on our discussion, I would make the **final architecture intentionally simple**, because your first version uses **mock incident inputs**, not a real Kubernetes/production environment.

The important point is that the system should demonstrate **AI incident investigation and decision-making**, without pretending to execute real infrastructure commands.

# Final AI Incident Triage Architecture

```text
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
```

---

# Explanation of Each Box

## 1. Incident Input

```text
┌──────────────────────────────┐
│       INCIDENT INPUT         │
│                              │
│ Mock Logs / Alerts / Events  │
│ Metrics / Deployment Data    │
└──────────────────────────────┘
```

### What does it do?

This is the **entry point** of the system.

For your initial project, we provide **mock incident data** instead of connecting to a real Kubernetes or cloud environment.

Example:

```text
Service: payment-service
Environment: production

Alert:
CrashLoopBackOff

Logs:
DATABASE_URL environment variable not found

Recent Deployment:
payment-service:v2.4
```

### Why do we need it?

It gives the AI enough information to start investigating an incident.

---

# 2. Incident Ingestion

```text
┌──────────────────────────────┐
│    INCIDENT INGESTION        │
│                              │
│ Normalize                    │
│ Deduplicate                  │
│ Correlate                    │
└──────────────────────────────┘
```

### What does it do?

It converts different input formats into a **standard incident structure**.

It also:

* Removes duplicate alerts
* Combines related alerts
* Identifies whether several alerts belong to the same incident

Example:

```text
Payment API 503
Pod Restarting
Database Connection Error
        ↓
     One Incident
```

### Why do we need it?

Monitoring systems can generate hundreds of alerts for one underlying problem.

This prevents the AI from treating every alert as a separate incident.

---

# 3. Incident Classifier

```text
┌──────────────────────────────┐
│    INCIDENT CLASSIFIER       │
│                              │
│ K8s / Application / DB       │
│ Network / IAM / Infra        │
└──────────────────────────────┘
```

### What does it do?

Determines **what type of incident** occurred.

Example:

```text
CrashLoopBackOff
       ↓
Kubernetes
```

Another example:

```text
AccessDeniedException
       ↓
IAM / Security
```

### Why do we need it?

Different incident categories require different investigation strategies and different responsible teams.

---

# 4. Impact Assessment

```text
┌──────────────────────────────┐
│     IMPACT ASSESSMENT        │
│                              │
│ Environment / Service        │
│ Users / Business Impact      │
└──────────────────────────────┘
```

### What does it do?

Determines **how serious the incident is from an operational/business perspective**.

It considers:

* Production vs development
* Critical vs non-critical service
* Number of users affected
* Service availability
* Business importance

Example:

```text
Production
+
Payment service unavailable
+
All users affected
        ↓
High Impact
```

### Why do we need it?

Technical severity and business impact are not always the same.

A failed development pod may be low priority, while a failed production payment service could be critical.

---

# 5. Severity Engine

```text
┌──────────────────────────────┐
│      SEVERITY ENGINE         │
│                              │
│       Rules + LLM            │
│          P1 / P2 / P3        │
└──────────────────────────────┘
```

### What does it do?

Assigns:

```text
P1
P2
P3
```

using a combination of **deterministic rules and LLM reasoning**.

Example:

```text
Environment = Production
Service = Payment
Users affected = All
Service status = Down

        ↓

Priority = P1
```

### Why do we need it?

We should **not rely only on the LLM** for priority.

Business rules should control critical decisions, while the LLM can provide additional reasoning.

---

# 6. Investigation Agent

This is the box we changed based on your mock-input approach.

```text
┌────────────────────────────────┐
│       INVESTIGATION AGENT      │
│                                │
│ Analyze Mock Evidence          │
│ Identify Symptoms              │
│ Generate Possible Hypotheses   │
│ Identify Missing Evidence      │
└────────────────────────────────┘
```

### What does it do?

It analyzes the evidence that was already provided in the mock incident.

It does **not** run:

```text
kubectl
aws
terraform
prometheus
```

against a real environment.

Instead, it reasons over the supplied data.

Example:

```text
Input:

CrashLoopBackOff

Log:
DATABASE_URL not found

Deployment:
v2.4 deployed 5 minutes ago
```

The agent may determine:

```text
Symptoms:
- Container restarting
- Application configuration missing

Possible Causes:
1. Missing Secret
2. Incorrect Deployment configuration
3. Application defect

Missing Evidence:
- Secret configuration
- Previous deployment configuration
```

### Why do we need it?

This is what makes the project an **AI Incident Investigation system rather than just an LLM classifier**.

The agent doesn't immediately guess the RCA.

It first asks:

> What do I know?
> What could be causing this?
> What evidence supports each possibility?
> What evidence is missing?

---

# 7. RCA Agent

```text
┌──────────────────────────────┐
│          RCA AGENT            │
│                              │
│ Evidence + Hypotheses        │
│ Root Cause + Confidence      │
└──────────────────────────────┘
```

### What does it do?

Takes the investigation findings and determines the **most likely root cause**.

Example:

```text
CrashLoopBackOff
       ↓
DATABASE_URL missing
       ↓
Deployment expects DATABASE_URL
       ↓
No matching Secret configuration
       ↓
Root Cause:
Missing Secret
```

Output:

```text
Root Cause:
Missing Kubernetes Secret

Confidence:
91%

Evidence:
- Application reports missing DATABASE_URL
- Deployment requires DATABASE_URL
- Service started failing after deployment
```

### Why do we need it?

It separates **investigation** from **root-cause determination**.

This makes the reasoning easier to understand and evaluate.

---

# 8. Knowledge Base / RAG

```text
┌──────────────────────────────┐
│       KNOWLEDGE BASE         │
│                              │
│ Runbooks / SOPs              │
│ Past Incidents / Postmortems │
│              RAG             │
└──────────────────────────────┘
```

### What does it do?

Retrieves relevant organizational knowledge.

You can store:

```text
Runbooks
SOPs
Kubernetes troubleshooting guides
Previous incidents
Postmortems
Resolution documents
```

Example:

```text
Current Incident
      ↓
Search Knowledge Base
      ↓
Similar Incident:
INC-1024
      ↓
Root Cause:
Secret configuration issue
      ↓
Previous Resolution
```

### Why do we need it?

The AI should not depend only on its general knowledge.

RAG gives it **company-specific troubleshooting knowledge**.

---

# 9. Resolution Planner

```text
┌──────────────────────────────┐
│     RESOLUTION PLANNER       │
│                              │
│ Recommended Actions          │
│ Runbook / Troubleshooting    │
└──────────────────────────────┘
```

### What does it do?

Creates a step-by-step recommended resolution.

Example:

```text
Recommended Actions:

1. Verify the Secret configuration
2. Restore missing DATABASE_URL
3. Restart the deployment
4. Validate pod health
5. Monitor application logs
```

### Why do we need it?

The output shouldn't only say:

> Root cause is a missing secret.

It should also tell the engineer:

> **What should I do next?**

---

# 10. Safety + Human Approval

```text
┌──────────────────────────────┐
│       SAFETY + APPROVAL      │
│                              │
│ Risk Check                   │
│ Human Approval               │
└──────────────────────────────┘
```

### What does it do?

Checks whether the recommended action is safe.

For your first version, **no real action is executed**.

The system only presents:

```text
Recommended Action:
Restart payment-service

Risk:
Medium

Environment:
Production

Approval:
Required
```

### Why do we need it?

It prevents the AI from becoming an uncontrolled automation system.

Later, you can add real remediation with explicit human approval.

---

# 11. Verification

Since your input is mocked, verification should also be based on **mock outcome data**.

```text
┌──────────────────────────────┐
│        VERIFICATION          │
│                              │
│ Mock Outcome Data            │
│ Is Incident Resolved?        │
└──────────────────────────────┘
```

### What does it do?

Checks whether the recommended resolution actually solved the incident.

For example:

```text
Before:

Pod Status = CrashLoopBackOff
HTTP = 503

       ↓
Resolution Applied
       ↓

Mock Result:

Pod Status = Running
HTTP = 200
Error Rate = Normal

       ↓

Incident Resolved
```

### Why do we need it?

An AI recommendation shouldn't automatically be considered successful.

The system needs to verify the outcome.

If verification fails:

```text
Verification Failed
       ↓
Investigation Agent
       ↓
New Investigation
```

This gives you a **feedback loop**.

---

# 12. Incident Report

```text
┌──────────────────────────────┐
│       INCIDENT REPORT        │
│                              │
│ Summary / Severity / Impact  │
│ RCA / Confidence / Actions   │
│ Team / Status                │
└──────────────────────────────┘
```

### What does it do?

Produces the final structured incident report.

Example:

```text
Incident:
Payment Service Failure

Environment:
Production

Priority:
P1

Category:
Kubernetes

Impact:
Payment transactions unavailable

Root Cause:
Missing Kubernetes Secret

Confidence:
91%

Recommended Actions:
1. Restore Secret
2. Restart Deployment
3. Validate application

Responsible Team:
DevOps

Status:
Resolved
```

### Why do we need it?

This gives engineers and management a **consistent incident summary**.

It can later be consumed by dashboards, Jira, Slack, Teams, or ServiceNow.

---

# 13. Notification / Ticketing

```text
┌──────────────────────────────┐
│    NOTIFICATION / TICKETING  │
│                              │
│ Jira / Slack / Teams         │
│ ServiceNow                   │
└──────────────────────────────┘
```

### What does it do?

Sends the final incident report to the appropriate systems.

For example:

```text
Incident
   ↓
AI Investigation
   ↓
RCA
   ↓
Human Approval
   ↓
Incident Report
   ↓
Create Jira Ticket
   +
Send Slack Notification
```

### Why do we need it?

The AI investigation should fit into the **existing incident-management process**, rather than becoming another isolated tool.

---

# Where LangChain, LangGraph and LangSmith fit

The architecture becomes much clearer if you show the frameworks separately:

```text
                  ┌──────────────────────────┐
                  │       LangGraph          │
                  │                          │
                  │ Orchestrates the entire  │
                  │ incident workflow        │
                  └────────────┬─────────────┘
                               │
        ┌──────────────────────┼─────────────────────┐
        │                      │                     │
        ▼                      ▼                     ▼
   LangChain                RAG                   Tools
   Components           Knowledge Base        Mock Tools
        │
        ▼
   LLM / Groq
```

### LangGraph

Controls the workflow:

```text
Classifier
    ↓
Severity
    ↓
Investigation
    ↓
RCA
    ↓
RAG
    ↓
Resolution
    ↓
Verification
```

### LangChain

Provides the building blocks:

* LLM integration
* Prompt templates
* Structured outputs
* RAG
* Retrievers
* Tool calling

### LangSmith

Observes the AI system:

```text
LangGraph
    ↓
LangSmith
    ↓
Trace each node
    ↓
Evaluate RCA
    ↓
Measure latency / tokens / cost
```

---



For a project like this, I'd structure it using **Clean Architecture + Domain-Driven Design (DDD)** principles. The key idea is:

* **LangGraph orchestrates** the workflow.
* **Agents contain reasoning**, not orchestration.
* **Tools only fetch/process data** (mock or real).
* **Business logic lives in services**, not inside prompts.
* **Models/schemas are shared across the application.**
* Every component is **replaceable and extensible**.

This structure lets you add a new agent later without modifying the rest of the project.

---

# Final Production Folder Structure

```text
ai-incident-triage/
│
├── app/
│   │
│   ├── main.py                     # Application entry point
│   ├── config.py                   # Application configuration
│   ├── dependencies.py             # Dependency injection
│   │
│   ├── graph/                      # LangGraph Orchestration
│   │   ├── workflow.py             # Graph definition
│   │   ├── state.py                # Global graph state
│   │   ├── router.py               # Conditional routing
│   │   ├── builder.py              # Graph builder
│   │   └── nodes/
│   │       ├── ingestion.py
│   │       ├── classification.py
│   │       ├── impact.py
│   │       ├── severity.py
│   │       ├── investigation.py
│   │       ├── rca.py
│   │       ├── knowledge.py
│   │       ├── resolution.py
│   │       ├── approval.py
│   │       ├── verification.py
│   │       ├── report.py
│   │       └── notification.py
│   │
│   ├── agents/                     # AI reasoning agents
│   │   ├── base.py
│   │   │
│   │   ├── classifier/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── impact/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── severity/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── investigation/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── rca/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── resolution/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   ├── report/
│   │   │   ├── agent.py
│   │   │   ├── prompt.py
│   │   │   └── parser.py
│   │   │
│   │   └── notification/
│   │       ├── agent.py
│   │       └── prompt.py
│   │
│   ├── domain/                     # Business domain
│   │   ├── models/
│   │   │   ├── incident.py
│   │   │   ├── evidence.py
│   │   │   ├── hypothesis.py
│   │   │   ├── impact.py
│   │   │   ├── severity.py
│   │   │   ├── root_cause.py
│   │   │   ├── resolution.py
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
│   ├── services/                   # Pure business logic
│   │   ├── ingestion_service.py
│   │   ├── correlation_service.py
│   │   ├── classification_service.py
│   │   ├── impact_service.py
│   │   ├── severity_service.py
│   │   ├── hypothesis_service.py
│   │   ├── evidence_service.py
│   │   ├── rca_service.py
│   │   ├── recommendation_service.py
│   │   ├── approval_service.py
│   │   ├── verification_service.py
│   │   ├── report_service.py
│   │   └── notification_service.py
│   │
│   ├── knowledge/                  # RAG
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
│   │       ├── classifier.txt
│   │       ├── impact.txt
│   │       ├── severity.txt
│   │       ├── investigation.txt
│   │       ├── rca.txt
│   │       ├── resolution.txt
│   │       ├── report.txt
│   │       └── notification.txt
│   │
│   ├── tools/                      # Tool abstraction
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
│   ├── rules/                      # Deterministic rules
│   │   ├── severity.py
│   │   ├── ownership.py
│   │   ├── impact.py
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

---

# Why this structure?

This follows a clear separation of responsibilities:

| Folder          | Responsibility                                    |
| --------------- | ------------------------------------------------- |
| `graph/`        | LangGraph orchestration only                      |
| `agents/`       | LLM reasoning                                     |
| `services/`     | Business logic                                    |
| `tools/`        | External integrations (mock today, real tomorrow) |
| `knowledge/`    | RAG implementation                                |
| `rules/`        | Deterministic business rules                      |
| `guardrails/`   | AI safety and validation                          |
| `domain/`       | Core business entities                            |
| `schemas/`      | Request/response and state models                 |
| `repositories/` | Data access layer                                 |
| `telemetry/`    | LangSmith and tracing                             |

---

# Adding a New Agent

This is designed to be **plug-and-play**.

Suppose you want to add a **Cost Optimization Agent** in the future.

You only add:

```text
agents/
    cost_optimizer/
        agent.py
        prompt.py
        parser.py

graph/
    nodes/
        cost_optimizer.py

prompts/
    templates/
        cost_optimizer.txt

services/
    cost_optimizer_service.py
```

Then register the new node in `graph/workflow.py`.

No existing agent, service, or tool needs to be modified.

---


# AI Incident Triage - Folder Structure Guide

This document explains the purpose of every folder and file in the project. Think of it as the architecture guide for anyone joining the project.

---

# Root Directory

```text
ai-incident-triage/
```

This is the root of the project. Everything inside is organized by responsibility so that the application remains modular, scalable, and easy to maintain.

---

# app/

```text
app/
```

This is the heart of the application.

It contains all the application logic, LangGraph workflow, AI agents, services, business models, LLM integrations, and supporting modules.

---

# main.py

```text
app/main.py
```

## Purpose

Main entry point of the application.

Responsible for:

* Starting the application
* Loading configuration
* Building the LangGraph workflow
* Receiving incident input
* Returning the final incident report

Think of this as:

> **Application Launcher**

---

# config.py

```text
app/config.py
```

## Purpose

Stores application configuration.

Examples

* API Keys
* Model Name
* Vector Store Path
* Confidence Threshold
* Logging Configuration
* Feature Flags

Instead of writing

```python
os.getenv(...)
```

throughout the project, everything is centralized here.

---

# dependencies.py

```text
app/dependencies.py
```

## Purpose

Creates shared objects used throughout the application.

Example

* LLM instance
* Embedding model
* Vector Store
* Logger
* Knowledge Retriever

Instead of creating them multiple times, the application reuses these objects.

---

# graph/

```text
app/graph/
```

## Purpose

Contains the **LangGraph workflow**.

This folder controls **how the incident moves through the system**.

It does **not** perform AI reasoning.

It only controls

```
Where to go next
```

---

# workflow.py

Defines the complete LangGraph workflow.

Example

```
Input

↓

Classification

↓

Severity

↓

Investigation

↓

RCA

↓

Resolution

↓

Verification

↓

Report
```

---

# builder.py

Creates the LangGraph object.

Registers

* Nodes
* Edges
* Conditional routing

---

# router.py

Contains decision-making logic.

Example

```
Confidence > 80%

↓

Continue

Else

↓

Re-investigate
```

---

# state.py

Defines the shared state flowing between every node.

Example

```python
Incident

Classification

Severity

Impact

Evidence

Hypothesis

Root Cause

Resolution

Report
```

Every node updates this object.

---

# graph/nodes/

```text
graph/nodes/
```

Each file represents **one LangGraph node**.

The node simply calls the appropriate service or AI agent.

Example

```
classification.py

↓

Calls

↓

Classifier Agent
```

This keeps orchestration separate from reasoning.

---

# agents/

```text
agents/
```

## Purpose

Contains every AI Agent.

Each agent performs one specific reasoning task.

The graph calls agents.

Agents never call the graph.

---

# base.py

Shared base class.

Provides

* LLM access
* Prompt execution
* Output parsing
* Error handling

Every agent inherits from this.

---

# classifier/

Responsible for identifying the incident category.

Example

```
CrashLoopBackOff

↓

Kubernetes
```

---

# impact/

Determines business impact.

Example

```
Production

↓

Payment Service

↓

High Impact
```

---

# severity/

Determines

```
P1

P2

P3
```

Uses

* Rules
* LLM reasoning

---

# investigation/

This is your AI Investigation Engineer.

Responsibilities

* Analyze incident evidence
* Identify symptoms
* Generate hypotheses
* Identify missing evidence

It never connects to a real Kubernetes cluster in your current project.

---

# rca/

Determines the most likely root cause.

Example

```
Missing Secret

Confidence 92%
```

---

# resolution/

Generates step-by-step resolution.

Example

```
Verify Secret

Restart Deployment

Validate Pods
```

---

# report/

Creates the final structured incident report.

---

# notification/

Generates Slack/Jira/Teams notifications.

---

# prompt.py

Contains the prompt used by that agent.

Each agent has its own prompt.

---

# parser.py

Converts raw LLM output into structured Pydantic objects.

Never trust raw LLM responses.

---

# domain/

```text
domain/
```

Contains the business objects used throughout the application.

Think of these as the language of your business.

---

# models/

Defines all entities.

Examples

```
Incident

Evidence

Hypothesis

Severity

Resolution

Report
```

These models are shared everywhere.

---

# enums/

Stores fixed values.

Example

```
Priority

P1

P2

P3
```

instead of strings.

---

# constants.py

Stores constants used throughout the application.

Example

```
Confidence Threshold

Default Namespace

Supported Categories
```

---

# services/

```text
services/
```

Contains business logic.

This folder answers

```
How should the application behave?
```

The services never know about prompts.

They never know about LangGraph.

They simply perform business operations.

Example

```
Severity Service

↓

Uses rules

↓

Returns

P1
```

---

# knowledge/

```text
knowledge/
```

Responsible for the RAG pipeline.

Everything related to knowledge retrieval lives here.

---

# loader.py

Loads documents.

---

# chunker.py

Splits documents into chunks.

---

# embeddings.py

Creates embeddings.

---

# vector_store.py

Stores embeddings.

---

# retriever.py

Retrieves relevant documents.

---

# llm/

```text
llm/
```

Contains LLM abstraction.

Never call Groq/OpenAI directly elsewhere.

---

# factory.py

Returns the configured LLM.

Example

```
Groq

OpenAI

Anthropic

Gemini
```

One interface.

---

# providers/

Each provider implementation.

Easy to switch models.

---

# structured_output.py

Converts LLM output into structured objects.

---

# prompts/

```text
prompts/
```

Stores every prompt outside Python code.

Makes prompt engineering easier.

---

# shared/

Reusable prompts.

Example

```
System Prompt

Output Format

Guardrails
```

---

# templates/

Agent-specific prompts.

Example

```
Classifier

Investigation

RCA

Resolution
```

---

# tools/

```text
tools/
```

Represents external systems.

Tools gather information.

They do not perform reasoning.

---

# mock/

Contains mock implementations.

Example

```
Mock Logs

Mock Events

Mock Metrics

Mock Deployments
```

Used for your project.

---

# adapters/

Real implementations.

Future examples

```
Kubernetes API

Prometheus

CloudWatch

Slack

Jira
```

Currently unused but production-ready.

---

# rules/

```text
rules/
```

Contains deterministic rules.

Never ask an LLM something that can be implemented with code.

Example

```
Production

+

Payment

↓

Always P1
```

---

# guardrails/

```text
guardrails/
```

Protects the AI.

Examples

* Prompt injection prevention
* Domain validation
* Safety checks
* Input validation

---

# repositories/

```text
repositories/
```

Responsible for reading and writing data.

Today

```
JSON
```

Tomorrow

```
PostgreSQL

MongoDB

S3
```

Nothing else changes.

---

# schemas/

```text
schemas/
```

Contains API contracts.

Defines

* Requests
* Responses
* Graph State
* Tool Outputs

Keeps communication consistent.

---

# utils/

```text
utils/
```

Common reusable helpers.

Examples

* Logging
* JSON utilities
* Time formatting
* Confidence calculations

---

# telemetry/

```text
telemetry/
```

Observability.

Responsible for

* LangSmith tracing
* Performance metrics
* Execution tracing

Useful during development and debugging.

---

# knowledge_base/

```text
knowledge_base/
```

Stores the documents used for RAG.

Examples

```
Runbooks

SOPs

Postmortems

Previous Incidents

Kubernetes Guides
```

These are indexed into the vector database.

---

# data/

```text
data/
```

Contains application data.

---

# incidents/

Mock incidents.

Example

```
CrashLoopBackOff

ImagePullBackOff

503

Database Timeout
```

These simulate production incidents.

---

# outcomes/

Mock verification data.

Example

```
Resolved

Unresolved
```

Used by the Verification Agent.

---

# reports/

Stores generated reports.

Useful for demos and future auditing.

---

# scripts/

```text
scripts/
```

Utility scripts.

These are one-time or maintenance tasks.

Examples

```
Seed mock data

Build vector store

Ingest documents
```

---

# .env.example

Template showing all required environment variables.

Never commit the real `.env`.

---

# .gitignore

Defines files Git should ignore.

Example

```
__pycache__

.env

venv

logs
```

---

# pyproject.toml

Modern Python project configuration.

Contains

* Project metadata
* Dependencies (if using modern packaging)
* Tool configuration (formatter, linter, etc.)

---

# requirements.txt

Lists Python package dependencies.

Useful for simple installation.

---

# README.md

The project's primary documentation.

Should include:

* Project overview
* Architecture diagram
* Folder structure
* Installation steps
* Configuration
* Running the project
* Sample incident input/output
* Team contribution guide

---

# LICENSE

Specifies how others may use, modify, and distribute the project.

---

# Overall Architecture Mapping

| Architecture Step         | Project Folder                                                                            |
| ------------------------- | ----------------------------------------------------------------------------------------- |
| Incident Input            | `data/`, `tools/mock/`                                                                    |
| Incident Ingestion        | `graph/nodes/ingestion.py`, `services/ingestion_service.py`                               |
| Incident Classification   | `agents/classifier/`, `services/classification_service.py`                                |
| Impact Assessment         | `agents/impact/`, `services/impact_service.py`                                            |
| Severity Engine           | `agents/severity/`, `rules/severity.py`, `services/severity_service.py`                   |
| Investigation             | `agents/investigation/`, `services/evidence_service.py`, `services/hypothesis_service.py` |
| RCA                       | `agents/rca/`, `services/rca_service.py`                                                  |
| Knowledge Retrieval (RAG) | `knowledge/`, `knowledge_base/`                                                           |
| Resolution Planning       | `agents/resolution/`, `services/recommendation_service.py`                                |
| Safety & Approval         | `guardrails/`, `services/approval_service.py`                                             |
| Verification              | `graph/nodes/verification.py`, `services/verification_service.py`                         |
| Incident Report           | `agents/report/`, `services/report_service.py`                                            |
| Notifications             | `agents/notification/`, `services/notification_service.py`, `tools/adapters/`             |

## Design Philosophy

The project follows a layered architecture with clear separation of concerns:

* **Graph** orchestrates the workflow.
* **Agents** perform AI reasoning.
* **Services** implement business logic.
* **Rules** contain deterministic decisions.
* **Tools** interact with external or mock systems.
* **Knowledge** powers the RAG pipeline.
* **Domain & Schemas** define the application's shared data models.

This separation makes the codebase easier to maintain, test, and extend. Adding a new agent or replacing a component typically affects only one layer, allowing the overall architecture to remain stable as the project grows.



