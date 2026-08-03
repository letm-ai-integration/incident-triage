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


# 📁 app/

## Purpose

The **application layer**. It contains the complete AI Incident Triage system including workflow orchestration, AI agents, business logic, RAG, and integrations.

```text
app/
├── main.py
├── config.py
└── dependencies.py
```

| File              | Purpose                                                                                |
| ----------------- | -------------------------------------------------------------------------------------- |
| `main.py`         | Starts the application and executes the LangGraph workflow.                            |
| `config.py`       | Loads application configuration, environment variables, and settings.                  |
| `dependencies.py` | Creates and manages shared dependencies like LLM, vector store, logger, and retriever. |

---

# 📁 graph/

## Purpose

The **LangGraph orchestration layer**. It controls how an incident flows through the AI system.

> **Responsibility:** Orchestrate the workflow (NOT AI reasoning).

```text
graph/
├── workflow.py
├── builder.py
├── router.py
├── state.py
└── nodes/
```

| File          | Purpose                                              |
| ------------- | ---------------------------------------------------- |
| `workflow.py` | Defines the complete AI Incident workflow.           |
| `builder.py`  | Builds and compiles the LangGraph graph.             |
| `router.py`   | Controls conditional routing between graph nodes.    |
| `state.py`    | Defines the shared graph state passed between nodes. |

---

# 📁 graph/nodes/

## Purpose

Each file represents **one step (node)** in the LangGraph workflow.

```text
nodes/
├── ingestion.py
├── classification.py
├── impact.py
├── severity.py
├── investigation.py
├── rca.py
├── knowledge.py
├── resolution.py
├── approval.py
├── verification.py
├── report.py
└── notification.py
```

| File                | Purpose                                               |
| ------------------- | ----------------------------------------------------- |
| `ingestion.py`      | Receives and normalizes incoming incident data.       |
| `classification.py` | Executes incident classification.                     |
| `impact.py`         | Determines business impact.                           |
| `severity.py`       | Determines incident priority (P1/P2/P3).              |
| `investigation.py`  | Performs AI investigation using available evidence.   |
| `rca.py`            | Determines the most probable root cause.              |
| `knowledge.py`      | Retrieves similar incidents and runbooks using RAG.   |
| `resolution.py`     | Generates recommended resolution steps.               |
| `approval.py`       | Performs safety validation and human approval checks. |
| `verification.py`   | Verifies whether the incident is resolved.            |
| `report.py`         | Generates the final structured incident report.       |
| `notification.py`   | Sends notifications to external systems.              |

---

# 📁 agents/

## Purpose

Contains all **AI reasoning agents**. Each agent performs exactly one AI task.

> **Responsibility:** Think, analyze, reason.

```text
agents/
├── base.py
├── classifier/
├── impact/
├── severity/
├── investigation/
├── rca/
├── resolution/
├── report/
└── notification/
```

| File/Folder | Purpose                                                       |
| ----------- | ------------------------------------------------------------- |
| `base.py`   | Base class providing common LLM functionality for all agents. |

---

## 📁 classifier/

```text
classifier/
├── agent.py
├── prompt.py
└── parser.py
```

| File        | Purpose                                      |
| ----------- | -------------------------------------------- |
| `agent.py`  | Classifies the incident type using the LLM.  |
| `prompt.py` | Stores the classifier prompt template.       |
| `parser.py` | Converts LLM output into structured objects. |

---

## 📁 impact/

| File        | Purpose                                     |
| ----------- | ------------------------------------------- |
| `agent.py`  | Determines business impact of the incident. |
| `prompt.py` | Prompt for impact analysis.                 |
| `parser.py` | Parses impact analysis output.              |

---

## 📁 severity/

| File        | Purpose                              |
| ----------- | ------------------------------------ |
| `agent.py`  | Predicts incident severity using AI. |
| `prompt.py` | Prompt for severity analysis.        |
| `parser.py` | Parses severity output.              |

---

## 📁 investigation/

| File        | Purpose                                         |
| ----------- | ----------------------------------------------- |
| `agent.py`  | Investigates evidence and generates hypotheses. |
| `prompt.py` | Prompt for investigation reasoning.             |
| `parser.py` | Parses investigation results.                   |

---

## 📁 rca/

| File        | Purpose                                            |
| ----------- | -------------------------------------------------- |
| `agent.py`  | Determines the root cause from collected evidence. |
| `prompt.py` | Prompt for root cause analysis.                    |
| `parser.py` | Parses RCA output.                                 |

---

## 📁 resolution/

| File        | Purpose                                      |
| ----------- | -------------------------------------------- |
| `agent.py`  | Generates recommended troubleshooting steps. |
| `prompt.py` | Prompt for resolution planning.              |
| `parser.py` | Parses resolution output.                    |

---

## 📁 report/

| File        | Purpose                                     |
| ----------- | ------------------------------------------- |
| `agent.py`  | Creates the final incident report.          |
| `prompt.py` | Prompt for report generation.               |
| `parser.py` | Parses the report into a structured format. |

---

## 📁 notification/

| File        | Purpose                                    |
| ----------- | ------------------------------------------ |
| `agent.py`  | Generates notification messages.           |
| `prompt.py` | Prompt for Slack/Jira/Teams notifications. |

---

# 📁 domain/

## Purpose

Contains the **core business models** shared across the application.

```text
domain/
├── models/
├── enums/
└── constants.py
```

---

## 📁 models/

| File              | Purpose                             |
| ----------------- | ----------------------------------- |
| `incident.py`     | Defines the Incident model.         |
| `evidence.py`     | Represents investigation evidence.  |
| `hypothesis.py`   | Represents possible causes.         |
| `impact.py`       | Defines impact details.             |
| `severity.py`     | Defines severity information.       |
| `root_cause.py`   | Defines RCA details.                |
| `resolution.py`   | Defines recommended actions.        |
| `approval.py`     | Defines approval status.            |
| `verification.py` | Defines verification results.       |
| `report.py`       | Defines the final report structure. |

---

## 📁 enums/

| File               | Purpose                                |
| ------------------ | -------------------------------------- |
| `priority.py`      | Defines P1/P2/P3 priority values.      |
| `incident_type.py` | Defines supported incident categories. |
| `environment.py`   | Defines deployment environments.       |
| `team.py`          | Defines ownership teams.               |
| `status.py`        | Defines incident status values.        |

| File           | Purpose                                |
| -------------- | -------------------------------------- |
| `constants.py` | Stores reusable application constants. |

---

# 📁 services/

## Purpose

Contains **business logic** independent of AI.

> **Responsibility:** Execute business rules, calculations, and processing.

| File                        | Purpose                                           |
| --------------------------- | ------------------------------------------------- |
| `ingestion_service.py`      | Processes and normalizes incoming incidents.      |
| `correlation_service.py`    | Correlates related alerts into a single incident. |
| `classification_service.py` | Business logic for classification.                |
| `impact_service.py`         | Calculates business impact.                       |
| `severity_service.py`       | Applies severity rules.                           |
| `hypothesis_service.py`     | Manages investigation hypotheses.                 |
| `evidence_service.py`       | Processes incident evidence.                      |
| `rca_service.py`            | Performs root cause analysis logic.               |
| `recommendation_service.py` | Generates recommended actions.                    |
| `approval_service.py`       | Performs approval validation.                     |
| `verification_service.py`   | Verifies incident resolution.                     |
| `report_service.py`         | Builds the final report.                          |
| `notification_service.py`   | Creates notification payloads.                    |

---

# 📁 knowledge/

## Purpose

Implements the **Retrieval-Augmented Generation (RAG)** pipeline.

| File              | Purpose                                     |
| ----------------- | ------------------------------------------- |
| `loader.py`       | Loads knowledge documents.                  |
| `chunker.py`      | Splits documents into chunks.               |
| `embeddings.py`   | Creates embeddings for documents.           |
| `vector_store.py` | Stores document embeddings.                 |
| `retriever.py`    | Retrieves relevant documents for AI agents. |

---

# 📁 llm/

## Purpose

Provides a unified interface for all supported LLM providers.

| File                   | Purpose                                          |
| ---------------------- | ------------------------------------------------ |
| `factory.py`           | Creates the configured LLM instance.             |
| `structured_output.py` | Converts raw LLM output into structured objects. |

### 📁 providers/

| File           | Purpose                |
| -------------- | ---------------------- |
| `groq.py`      | Groq LLM integration.  |
| `openai.py`    | OpenAI integration.    |
| `anthropic.py` | Anthropic integration. |
| `gemini.py`    | Gemini integration.    |

---

# 📁 prompts/

## Purpose

Stores all prompt templates separately from Python code.

### 📁 shared/

| File                | Purpose                                          |
| ------------------- | ------------------------------------------------ |
| `system_prompt.txt` | Global system instructions shared by all agents. |
| `output_format.txt` | Standard output format for AI responses.         |
| `guardrails.txt`    | AI safety and behavior guidelines.               |

### 📁 templates/

Each file contains the prompt template for its corresponding AI agent.

| File                | Purpose                         |
| ------------------- | ------------------------------- |
| `classifier.txt`    | Incident classification prompt. |
| `impact.txt`        | Impact assessment prompt.       |
| `severity.txt`      | Severity analysis prompt.       |
| `investigation.txt` | Investigation prompt.           |
| `rca.txt`           | Root cause analysis prompt.     |
| `resolution.txt`    | Resolution planning prompt.     |
| `report.txt`        | Report generation prompt.       |
| `notification.txt`  | Notification generation prompt. |

---

# 📁 tools/

## Purpose

Provides access to external or mock systems.

### 📁 mock/

Contains mock implementations for development.

| File             | Purpose                          |
| ---------------- | -------------------------------- |
| `logs.py`        | Provides mock application logs.  |
| `metrics.py`     | Provides mock metrics.           |
| `deployments.py` | Provides mock deployment data.   |
| `events.py`      | Provides mock Kubernetes events. |
| `alerts.py`      | Provides mock alert data.        |

### 📁 adapters/

Contains real production integrations.

| File            | Purpose                     |
| --------------- | --------------------------- |
| `kubernetes.py` | Kubernetes API integration. |
| `prometheus.py` | Prometheus integration.     |
| `cloudwatch.py` | CloudWatch integration.     |
| `jira.py`       | Jira integration.           |
| `slack.py`      | Slack integration.          |
| `servicenow.py` | ServiceNow integration.     |

---

The remaining folders follow the same pattern:

| Folder            | Purpose                                                                               |
| ----------------- | ------------------------------------------------------------------------------------- |
| `rules/`          | Stores deterministic business rules (severity, ownership, confidence).                |
| `guardrails/`     | Implements AI safety, validation, and prompt protection.                              |
| `repositories/`   | Handles reading and writing application data.                                         |
| `schemas/`        | Defines request, response, and graph state schemas.                                   |
| `utils/`          | Contains reusable helper utilities used across the project.                           |
| `telemetry/`      | Provides LangSmith tracing, logging, and application metrics.                         |
| `knowledge_base/` | Stores runbooks, SOPs, postmortems, and documents used by RAG.                        |
| `data/`           | Contains mock incidents, verification outcomes, and generated reports.                |
| `scripts/`        | Utility scripts for seeding data, building the vector store, and ingesting knowledge. |

This documentation style is commonly used in production repositories because a new developer can understand the purpose of every folder and file without reading the implementation.

