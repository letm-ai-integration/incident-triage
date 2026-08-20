# Notification Agent — Instruction File for OpenCode

**Scope:**

```
app/agents/notification/              — agent.py, prompt.py (primary work)
app/tools/adapters/                   — NEW: resend_email.py (mirrors
                                         existing adapter pattern:
                                         slack.py, jira.py, servicenow.py)
app/tools/mock/                       — NEW: oncall.py (mirrors existing
                                         mock pattern: alerts.py, logs.py)
data/                                 — NEW: mock on-call/support contact
                                         text file (location per §0.6)
app/config.py                         — add RESEND_API_KEY + related settings
.env.example                          — add RESEND_API_KEY + related vars
app/domain/models/ or app/schemas/    — only if a genuinely new small model
                                         is needed (e.g. on-call contact
                                         shape); reuse existing first
app/services/notification_service.py — touch ONLY if inspection (§0.3)
                                         shows it already owns
                                         recipient-resolution/dispatch
                                         responsibility for this agent;
                                         otherwise leave untouched
tests/                                — this agent + new adapter/mock only
```

**Do not touch:** `app/graph/` (any file), any other agent under
`app/agents/`, `app/guardrails/`, or unrelated tools/adapters. Minimal,
clean changes only — reuse existing patterns everywhere they already fit;
do not introduce a new architectural style for this one agent.

---

## 0. Mandatory First Step — Inspect Before You Write

1. **Read `app/agents/classification/` in full**
   (`agent.py`, `prompt.py`, `parser.py`) — this is the one fully
   completed agent in the project. Use it to understand:
   - How the agent obtains an LLM (whatever client/factory pattern is
     currently in use).
   - How `prompt.py` loads/renders a template from `app/prompts/`.
   - How `parser.py` turns LLM output into a structured object.
   - How errors are raised and how `agents/base.py` is used, if at all.

   **This is for structural/convention reference only** — classification
   classifies incidents; notification sends an email. Do not copy its
   *logic*, only its *shape and conventions* (imports, naming, error
   handling, LLM access) so the new agent fits the codebase.

2. **Read `app/agents/investigation/orchestrator.py` and
   `app/graph/nodes/notification.py`** (if it already has any content) to
   confirm what actually reaches the notification stage in the pipeline —
   per the node order (`rca_report → approval → verification →
   notification`), confirm whether notification receives the RCA report
   directly, or a wrapped/combined state object that includes it.
   Regardless of what else is available, **the RCA report is the primary
   input this agent acts on** — confirm its exact model.

3. **Read `app/domain/models/report.py`** — this is almost certainly the
   RCA report model. Confirm its fields (summary, root cause, resolution
   steps, affected service, severity, etc.) — the email content should be
   composed from these fields, not invented.

4. **Read `app/services/notification_service.py`** as it exists today.
   Determine whether it's a stub or already contains logic that should own
   "resolve recipient" + "dispatch" responsibility (a common layered
   pattern in this project: agent = LLM/content generation,
   service = orchestration/dispatch, tools/adapters = external I/O). If it
   already does this for other channels (e.g. Slack), **follow that same
   split** for email rather than putting dispatch logic inside `agent.py`.
   If it's empty/unused, keep the dispatch logic inside `agent.py` for
   now — don't build out a bigger service layer than the codebase
   currently has.

5. **Read `app/tools/adapters/slack.py` and `jira.py`** (or
   `servicenow.py`) — these are the existing pattern for external-service
   integrations (auth/config loading, request construction, error
   handling, return shape). The new `resend_email.py` adapter must mirror
   this exactly, not invent a different integration style.

6. **Read `app/tools/mock/alerts.py`** (or another `tools/mock/*.py` file)
   for the existing mock-data convention, and check the `data/` folder's
   existing structure (`data/incidents/`, `data/outcomes/`, `data/reports/`)
   for where a new mock text file would fit most naturally — likely a new
   `data/oncall/` (or similarly named) folder, consistent with the
   existing one-concern-per-subfolder pattern. Confirm before creating.

7. **Read `app/prompts/templates/notification.txt`** — this file already
   exists; reuse and extend it for the email-composition prompt instead of
   inlining a new prompt string.

8. **Read `app/config.py`** for the existing settings pattern (see prior
   LLM-provider work if already applied) — new Resend settings must follow
   the same style, added additively.

9. **Check `pyproject.toml`/`requirements.txt`** for whether the `resend`
   Python package is already a dependency; add it if not, and confirm no
   equivalent email-sending library is already present and preferred.

---

## 1. What the Notification Agent Does

**Input:** the RCA report (§0.3) for a resolved/investigated incident.

**Process:**
1. Look up the current on-call/support developer from the mock data source
   (§2) — this is a **deterministic lookup**, not an LLM decision. There is
   exactly one "current support dev" in the mock data for now.
2. Use an LLM to compose a clear, concise notification email (subject +
   body) from the RCA report's actual fields — summary, root cause,
   resolution steps, severity, affected service. The LLM's job is
   *drafting readable prose from structured data*, not deciding facts not
   present in the report.
3. Send the email via the Resend adapter (§3) to the looked-up dev's email
   address.
4. Return a result indicating success or failure of the send (§5) — do not
   swallow adapter errors silently.

---

## 2. Mock On-Call/Support Data

Create a simple, human-readable text file (exact location confirmed in
§0.6) representing the current support developer:

```
Name: Ayush Sharma
Role: Backend On-Call Engineer
Email: ayush.sharma@example.com
Team: backend
Status: on-call
```

Keep the format as plain `Key: Value` lines — no need for JSON/YAML for a
single-record mock file, and it stays trivially human-editable, matching
the intent of a placeholder "whoever's currently on support" file that
someone can hand-edit until a real on-call system is integrated.

### `app/tools/mock/oncall.py` (NEW)

```python
"""
Mock on-call/support contact lookup. Reads a single current on-call
record from a plain-text file. Replace with a real on-call system
integration (PagerDuty, Opsgenie, etc.) later — see §9.
"""
from pathlib import Path
from dataclasses import dataclass

ONCALL_FILE_PATH = Path("data/oncall/current_oncall.txt")  # confirm path per §0.6


@dataclass(frozen=True)
class OnCallContact:
    name: str
    role: str
    email: str
    team: str
    status: str


def get_current_oncall() -> OnCallContact:
    if not ONCALL_FILE_PATH.exists():
        raise FileNotFoundError(f"On-call mock data file not found: {ONCALL_FILE_PATH}")

    fields = {}
    for line in ONCALL_FILE_PATH.read_text(encoding="utf-8").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip().lower()] = value.strip()

    return OnCallContact(
        name=fields["name"],
        role=fields["role"],
        email=fields["email"],
        team=fields["team"],
        status=fields["status"],
    )
```

If `OnCallContact` overlaps meaningfully with an existing model in
`domain/models/` (unlikely, given none of the listed files represent a
person/contact — but confirm), reuse that instead of this dataclass.

---

## 3. Resend Email Adapter

### `.env.example` — add

```env
# --- Email (Resend) ---
RESEND_API_KEY=your_resend_api_key_here
RESEND_FROM_EMAIL=alerts@yourdomain.com
RESEND_FROM_NAME=Incident Triage Bot
```

### `app/config.py` — add (following existing settings style)

```python
resend_api_key: str | None = None
resend_from_email: str = "alerts@yourdomain.com"
resend_from_name: str = "Incident Triage Bot"
```

### `app/tools/adapters/resend_email.py` (NEW)

Mirror the exact structure/conventions of `slack.py`/`jira.py` from §0.5
(error handling style, return type, how config is accessed) — the
template below is illustrative:

```python
"""
Resend email adapter. Thin wrapper — no business logic, no recipient
resolution. Callers pass a fully-formed message; this module only sends it.
"""
import resend
from app.config import get_settings


class EmailSendError(Exception):
    pass


def send_email(to: str, subject: str, html_body: str) -> str:
    """Sends an email via Resend. Returns the Resend message id on success."""
    settings = get_settings()
    if not settings.resend_api_key:
        raise EmailSendError("RESEND_API_KEY is not configured")

    resend.api_key = settings.resend_api_key

    try:
        response = resend.Emails.send({
            "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
            "to": [to],
            "subject": subject,
            "html": html_body,
        })
    except Exception as e:
        raise EmailSendError(f"Failed to send email via Resend: {e}") from e

    return response.get("id", "")
```

Match the actual `resend` Python SDK's real call signature — confirm
against the installed package version rather than assuming the exact
shape above.

---

## 4. Agent Implementation

### `app/agents/notification/agent.py`

```python
"""
Notification agent: composes and sends an email summarizing a resolved
incident's RCA report to the current on-call/support developer.
"""
from app.agents.notification.prompt import build_notification_prompt
from app.tools.mock.oncall import get_current_oncall
from app.tools.adapters.resend_email import send_email, EmailSendError
# LLM import: mirror whatever app/agents/classification/agent.py uses (§0.1)


def run_notification_agent(rca_report) -> "NotificationResult":
    contact = get_current_oncall()

    prompt = build_notification_prompt(rca_report=rca_report, contact=contact)
    # llm_response = <same LLM pattern as classification agent>(prompt)
    subject, html_body = _extract_email_content(llm_response)  # or via parser.py if one is added

    try:
        message_id = send_email(to=contact.email, subject=subject, html_body=html_body)
    except EmailSendError as e:
        return NotificationResult(success=False, error=str(e))

    return NotificationResult(success=True, recipient=contact.email, message_id=message_id)


def _extract_email_content(llm_response) -> tuple[str, str]:
    """Split LLM output into (subject, html_body). Keep this simple —
    e.g. a structured JSON response from the LLM with 'subject' and
    'body' keys, parsed the same way classification's parser.py parses
    its LLM output, per §0.1."""
    ...
```

### `app/agents/notification/prompt.py`

- Load/extend `app/prompts/templates/notification.txt` (§0.7).
- Instruct the LLM to: write a clear subject line naming the incident and
  severity, and a body summarizing root cause, impact, and resolution
  steps from the RCA report — using only information present in the
  report, no invented details.
- Ask for structured output (e.g. `{"subject": ..., "body": ...}`) so
  parsing stays simple and consistent with how classification's LLM
  output is parsed (§0.1).

### Result type

Keep this minimal — a small dataclass or, if the project has an existing
generic result pattern (check `graph/state.py` if this agent needs to
report into state, though wiring into the graph itself is **out of
scope** for this task per the "do not touch `app/graph/`" rule):

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class NotificationResult:
    success: bool
    recipient: str | None = None
    message_id: str | None = None
    error: str | None = None
```

Place this in `agent.py` itself unless the project convention (per §0.1)
puts such result types elsewhere.

---

## 5. Domain Models/Schemas — Only If Genuinely Needed

Per §2, `OnCallContact` is a small, self-contained shape used only by the
mock lookup + agent — keep it local to `tools/mock/oncall.py` unless
inspection (§0.6) shows the project already has a "contact"/"person" model
elsewhere that should be reused instead. Do not create a new file in
`domain/models/` for a four-field mock record unless there's a real reason
to promote it there.

---

## 6. Tests

Location: `tests/agents/notification/` (and
`tests/tools/adapters/test_resend_email.py`,
`tests/tools/mock/test_oncall.py`), matching whatever `tests/` convention
already exists.

1. **`get_current_oncall()`** returns the correct `OnCallContact` from the
   mock file; raises `FileNotFoundError` if the file is missing.
2. **`send_email()`** calls the Resend SDK with correctly formed
   arguments (mock the `resend` package); raises `EmailSendError` on
   failure or missing API key.
3. **`run_notification_agent()`**:
   - Success path: given a sample RCA report, produces a `NotificationResult(success=True, ...)`, with the LLM and `send_email` mocked.
   - Email send failure: `send_email` raises → agent returns
     `NotificationResult(success=False, error=...)`, not an uncaught
     exception.
   - Confirm the composed email content actually reflects fields from the
     input RCA report (not hardcoded/generic text) using a mocked LLM
     response.

No test should send a real email or hit the real Resend API — mock the
adapter boundary.

---

## 7. Rules for OpenCode

You **must not**:

1. Touch `app/graph/` in any way — this agent must be callable
   standalone; wiring it into the graph is a separate task.
2. Touch any other agent under `app/agents/`.
3. Put recipient-resolution or email-dispatch logic inside
   `app/services/notification_service.py` unless §0.3 confirms that file
   already owns this responsibility for other channels — don't expand the
   service layer speculatively.
4. Invent a new LLM-access pattern — mirror classification's exactly
   (§0.1), even if you think a different pattern would be cleaner; this is
   about minimal, consistent change, not redesign.
5. Let the LLM invent RCA facts not present in the input report.
6. Hardcode the Resend API key, from-address, or on-call file path inline
   in `agent.py` — these belong in `config.py`/the mock file path constant.
7. Add the `resend` dependency without first confirming (§0.9) it isn't
   already present or superseded by something else in the project.
8. Create new top-level folders — `data/oncall/` (or wherever §0.6
   confirms) and `app/tools/adapters/resend_email.py` /
   `app/tools/mock/oncall.py` are the only new files/locations; everything
   else is additive within existing files.

---

## 8. Validation Criteria

- [ ] `get_current_oncall()` correctly parses the mock text file into an
      `OnCallContact`.
- [ ] `send_email()` correctly calls the Resend SDK with the configured
      `RESEND_API_KEY`/from-address, and raises `EmailSendError` cleanly
      on failure or missing key.
- [ ] `run_notification_agent(rca_report)` composes an email whose content
      is traceably derived from the input RCA report's actual fields.
- [ ] A failed send is reported as `NotificationResult(success=False,
      error=...)`, never an uncaught exception bubbling out of the agent.
- [ ] `.env.example` and `config.py` contain the new Resend settings,
      following the existing settings style exactly.
- [ ] No changes exist outside the scope listed at the top of this file.
- [ ] All new tests pass with the LLM, Resend SDK, and file I/O mocked —
      no real network calls in tests.

---

## 9. Future Extensions (not in current scope)

- **Real on-call system integration:** replace `tools/mock/oncall.py`'s
  text-file read with a PagerDuty/Opsgenie API call — the `OnCallContact`
  shape and `get_current_oncall()` signature can stay the same, keeping
  the agent itself unaffected.
- **Multiple recipients / escalation policy:** notifying a team channel in
  addition to/instead of a single dev, based on severity.
- **Delivery tracking:** persisting `message_id`/send status via
  `repositories/report_repository.py` or similar for auditability.
- **Retry logic:** automatic retry on transient Resend failures.
- **Graph wiring:** registering this agent as a node in
  `graph/nodes/notification.py` and connecting it via `builder.py` — a
  separate task, per the graph integration spec.

Do not implement any of the above unless explicitly requested.
