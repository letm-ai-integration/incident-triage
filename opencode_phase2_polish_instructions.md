# Phase-2 Polish Instructions: Email Template, Sidebar, Node Detail Layout, Label Formatting, Graph Pruning

You previously completed the accuracy/mock-data work from `master_accuracy_mockdata_instructions.md` — that work is done and must not be touched or regressed by anything below. This is a separate, follow-up set of five polish tasks, based on direct review of the running UI (screenshot attached in the conversation this was written from).

**Work through these five phases strictly in order, one at a time. After completing each phase — including its own verification — stop, summarize exactly what you did, and explicitly ask for confirmation before starting the next phase. Do not combine phases. Do not skip ahead.**

General ground rules for all five phases: analyze the actual existing code before editing; keep changes additive/scoped to what's asked; do not regress anything already working (graph execution, live status, run history, active-node data correctness, evidence/validation logic from the previous task).

---

## PHASE 1 — Convert the notification/report into a fixed-structure HTML/CSS template

### The problem
The notification is currently plain text (see the earlier "Incident Overview / Root Cause Analysis / Recommended Remediation / Investigation Status" example). It needs to become a proper HTML/CSS-styled document with a **fixed visual structure** — the same headings, layout, and styling every time — where only the underlying data changes per incident. Design decisions below are deliberate; implement them as specified rather than inventing an alternate layout, but the underlying data-binding approach (how you wire real fields into the template) should follow whatever the existing report-generation code already does structurally.

### Required template structure (single reusable HTML file, e.g. `templates/incident_report_email.html`, populated by the validated investigation result — never generated ad hoc per incident)

Use a **table-based HTML layout with inline CSS**, not flexbox/grid/external stylesheet — this is a hard requirement, not a style preference: most corporate email clients (Outlook in particular) only reliably render inline-styled `<table>` layouts, and a grid/flexbox-based email will render broken for a large fraction of recipients. If this same HTML is also going to be shown inside the Streamlit UI as a rendered report, it will still render correctly there since inline-styled tables are valid HTML — so this one template can safely serve both purposes.

**Header band** (top of the email, full width, colored background using the app's existing coral/red accent as the banner color):
- Incident ID (large, bold)
- A severity badge: `P1`/`P2`/`P3`/`P4` (or `Not specified` if truly absent from the incident data) — color-coded: P1 = red, P2 = orange, P3 = amber/yellow, P4 = gray, `Not specified` = neutral gray.
- Generated timestamp (small, right-aligned or below the ID).

**Body, sections in this exact fixed order, each as its own visually distinct block** (light background, generous padding, a clear heading in the accent color, consistent heading font size/weight across all sections so it reads as one coherent document):

1. **Incident Overview** — the narrative paragraph.
2. **Environment** — a single labeled line/badge, e.g. `Environment: Production`.
3. **Impacted Services** — an HTML table with columns `Service`, `Severity / Role`, `Impact`.
4. **Impact Assessment** — a narrative paragraph.
5. **Investigation Findings** — a bulleted (`<ul>`) list.
6. **Root Cause Analysis** — the root-cause state as a colored badge (`Confirmed` = green, `Probable` = amber, `Root cause could not be conclusively determined` = gray) followed by the explanation text, then `Contributing Factors`.
7. **Recommended Remediation** — either a numbered (`<ol>`) list of runbook steps, or, when no runbook was found, a visually distinct callout box (light amber/warning-tinted background, bordered) containing the "Runbook remediation unavailable... On-call engineering action is required" message from the existing template rules.
8. **Investigation Status** — three labeled rows/badges: `Investigation` (Completed/In Progress), `Root-Cause Analysis` (Confirmed/Probable/Inconclusive), `Remediation` (Not Applied/Applied/Pending On-Call Action) — each remediation state gets its own badge color: `Not Applied` = gray, `Pending On-Call Action` = amber, `Applied` = green. Below these, keep the existing italic disclaimer line ("This investigation is limited to analysis and recommendation...").

**Footer band** (small, muted text): the run ID and a one-line reminder that this is an automated investigation report.

### Edge-case handling — this is the part that actually matters, implement every one of these explicitly, do not let any of them render as blank space or a template error

- Missing/unknown environment → render `Environment: Not specified`, do not omit the section or leave it blank.
- Missing/unknown priority/severity → render the `Not specified` gray badge described above, never omit the badge entirely (a missing badge looks like a rendering bug, not "no data").
- Empty `Impacted Services` → render the table with a single row spanning all columns: `No impacted services could be identified from available evidence.`
- Empty `Investigation Findings` → render a single list item: `No findings could be established from available evidence.`
- No root cause determined → this already has a defined state (`Root cause could not be conclusively determined`) — use it, badge it gray, and still show whatever partial reasoning/evidence text exists rather than leaving the section empty.
- No matching runbook → use the existing "Runbook remediation unavailable" callout, never leave `Recommended Remediation` blank or show an empty list.
- Any field that is `None`/missing/empty string at render time must resolve to an explicit human-readable fallback string — never let a raw `None`, `null`, `undefined`, or empty `<td></td>` reach the rendered output.
- Long text (a very detailed Incident Overview, many findings, many table rows) must not break the layout — use normal text wrapping, do not truncate silently.
- HTML-escape all data values that come from incident text/logs before inserting them into the template, so incident descriptions containing `<`, `>`, `&`, or quotes can never break the HTML structure or (worse) inject markup.

### Verification before moving to Phase 2
- [ ] Render the template for `INC-006` (has a runbook, has clear environment/priority) and for at least one incident where you can force a missing field (e.g. temporarily blank the environment) to confirm the fallback renders correctly, then revert the forced blank.
- [ ] Open the rendered HTML output directly (not just eyeball the code) and confirm every one of the 8 body sections plus header/footer actually appears, styled, in the correct order.
- [ ] Confirm no `None`/`null`/empty-tag artifacts appear anywhere in the rendered output.

---

## PHASE 2 — Sidebar: remove the "Use LLM-backed agents" checkbox, and redesign the status display at the bottom

### 2.1 Remove the checkbox
Remove the "Use LLM-backed agents" checkbox from the left "Run options" panel entirely — including its associated help/tooltip icon. Before removing it, check what this checkbox currently *controls* in the code (it very likely toggles whether LLM-backed agents run vs. a deterministic/mock path). Since LLM-backed agents should now always run this option is being removed rather than just hidden — confirm with the underlying code path that removing the UI control means the LLM-backed path becomes the permanent/default behavior (not that the feature silently stops working because a required flag is never set now that its only UI toggle is gone). If the "LLM provider configured: yes" indicator beneath it existed specifically to explain the checkbox, keep the "LLM provider configured" indicator on its own — it's still useful independent of the checkbox — but see 2.2 below for how it should be presented.

### 2.2 Redesign the status area at the bottom of the sidebar
Right now the left sidebar has a long vertical "Status legend" list (Pending / Running / Success / Error / Started / Completed, each as its own full row with a dot and label) sitting permanently expanded, taking up a large fixed amount of vertical space above "Run history." This is more space than a reference legend needs once a user has seen it a couple of times.

Replace it with a **collapsible legend**: by default, show it collapsed as a single compact row — a small heading like "Status legend" with a chevron/disclosure icon — and only expand into the full list of colored dot+label rows when the user clicks it. This keeps the sidebar compact for the common case (user already knows the colors) while keeping the reference available on demand. Preserve every existing status/color pairing exactly as-is (Pending, Running, Success, Error, Started, Completed) — this is a layout change, not a content change. Also fold the "LLM provider configured: yes/no" indicator into this same compact status area (e.g. as a small badge/line near the top of the collapsed legend row, or immediately above it) rather than leaving it stranded where the removed checkbox used to be.

### Verification before moving to Phase 3
- [ ] The "Use LLM-backed agents" checkbox is fully gone from the UI, and a real run still correctly uses LLM-backed agents (confirm by running an incident and checking `agent_trace` entries are still populated, not just that the app doesn't crash).
- [ ] The status legend is collapsed by default, expands/collapses correctly on click, and every original status/color pairing is unchanged.
- [ ] The "LLM provider configured" indicator is still visible somewhere sensible in the sidebar.

---

## PHASE 3 — Move the Active Node Detail panel from a side column into a collapsible row above the graph

### The problem
"Active node · detail" currently sits as a tall right-hand column next to the graph canvas, always fully expanded, taking a large fixed amount of horizontal and vertical space regardless of whether the user wants to see it.

### What to build instead
Move it to sit **as a horizontal row directly above the "Graph canvas" section**, spanning the same width as the graph area below it. This row has two states:

- **Collapsed (default state):** a single compact bar showing just the essentials at a glance — the active node's name (using the humanized formatting from Phase 4 below), its status badge (color-coded exactly as the graph nodes are), and the elapsed time (e.g. "16.85 s") — everything currently shown at the very top of the detail panel in the screenshot, just condensed into one row instead of a whole column.
- **Expanded (on click):** reveals the rest of the detail content that currently lives in the column — Input state slice, Output, agent trace, etc. — inside a container with a **generous but fixed maximum height** (large enough to comfortably read a chunk of JSON/log content without feeling cramped — target roughly 400–500px, but use your judgment based on how this looks against the graph canvas height once built) and `overflow-y: auto` so long content scrolls *within that row's expanded area*, never pushing the graph canvas down the page or growing to fill the whole viewport. Collapsing it back should return to the compact single-line bar.

This directly parallels the fixed-height/scrollable treatment already applied to the old column version — the only structural change here is orientation (row-above-graph instead of column-beside-graph) and adding the collapse/expand interaction so the default state is compact.

### Verification before moving to Phase 4
- [ ] The detail area is now positioned above the graph canvas, spans its width, and is collapsed by default showing only name/status/elapsed-time.
- [ ] Clicking it expands to show the full input/output/agent-trace content, capped at a fixed generous height, scrollable within that container.
- [ ] Expanding it does not push the graph canvas or the rest of the page down/around — the page layout stays stable.
- [ ] Live updates (the detail auto-following the currently running node, per earlier work) still function correctly in this new layout.

---

## PHASE 4 — Humanize node/agent labels everywhere they're displayed

### The problem
Node and sub-agent names currently render as raw internal identifiers — `investigation_summary`, `log_analysis`, `rca_report` — which reads like exposed code/variable names, not a polished product UI.

### What to build
Write one small, reusable formatting utility (e.g. `ui/format_label.py::humanize_node_name(name: str) -> str`) and use it **everywhere** a node or sub-agent name is rendered — the graph canvas node boxes, the sub-agent pills inside `investigation`, the Active Node Detail bar (Phase 3), the execution timeline, and the Run History labels if they reference node names anywhere.

Default behavior: split on underscores, title-case each word, join with spaces (`investigation_summary` → `Investigation Summary`, `log_analysis` → `Log Analysis`).

But **do not stop at generic title-casing** — maintain an explicit override dictionary in the same utility for known acronyms/proper nouns so they render correctly instead of being naively title-cased:
- `rca_report` → `RCA Report` (not "Rca Report")
- `kubernetes` → `Kubernetes` (already fine, but confirm no incorrect casing occurs if it's ever compound, e.g. `k8s_diagnostics` → `Kubernetes Diagnostics`, not "K8S Diagnostics")
- Add any other real node/sub-agent names you find during Phase 1's original audit that don't title-case cleanly (check the actual node list from `NOTES.md`/`get_graph_topology()` for anything else like this — e.g. an `api`, `db`, `dns`, `tls` in a node name should also get correct-casing overrides).

This utility must be driven by the override dictionary first, falling back to the generic split-and-title-case rule for anything not explicitly listed — so any future node name automatically gets a reasonable default without needing a code change, while known-tricky names always render correctly.

### Verification before moving to Phase 5
- [ ] Every place a node/sub-agent name is displayed in the UI (graph canvas, sub-agent pills, Active Node Detail, timeline) goes through the new utility — spot-check by running an incident that exercises `investigation` (with its sub-agents) and `rca_report` and confirming both render in clean, spaced, correctly-cased human-readable form with no underscores anywhere in the UI.
- [ ] The underlying node/sub-agent identifiers used internally by the graph and event system are unchanged — this is a display-only transformation, not a rename of the actual graph nodes.

---

## PHASE 5 — Prune unused graph elements: verify, then remove if truly dead, then regenerate the graph diagram

### The problem
Looking at the current graph, there are two elements whose purpose is unclear from the UI alone:
1. A dashed edge running from `classification` directly to `notification` (labeled `auto_resolve` in the screenshot), bypassing the rest of the pipeline.
2. The `investigation_summary` node, sitting between `investigation` and `rca_report`.

**Do not remove either of these yet.** First, investigate whether they are actually live, reachable parts of the graph logic or genuinely dead/unused. This matters because the `auto_resolve` edge in particular looks like it could be an intentional conditional branch (e.g. "if classification determines the incident can be auto-resolved without investigation, skip straight to notification") rather than dead code — removing a live conditional branch would be a real regression, not a cleanup.

### What to do, in order

1. **For the `classification → notification` (`auto_resolve`) edge:** find the conditional-edge/routing function in `graph/` that defines this transition. Determine: under what actual condition does the graph take this path? Is there any code path, test, or mock incident that ever triggers `auto_resolve` (e.g. a classification result with very high confidence and low severity)? If you find real logic that can genuinely route this way, **do not remove it** — instead, report back what condition triggers it, and we'll decide together whether it's still wanted. If, after checking, this edge is dead — no routing function ever actually returns/selects it, or the condition can never be satisfied given current classification logic — then it's safe to remove.
2. **For the `investigation_summary` node:** find its implementation and determine what it actually does with the state — does it transform/summarize data in a way that `rca_report` (or anything downstream) actually depends on? Check whether removing it and wiring `investigation` directly to `rca_report` would silently drop any data `rca_report` currently relies on. If its output is unused or fully redundant with what `investigation` or `rca_report` already do on their own, it's safe to remove. If it's doing real, necessary transformation work, **do not remove it** — report back what it does and we'll decide together.
3. **Only after confirming (1) and (2) are genuinely dead:** remove the edge and/or node from the **backend graph definition** in `graph/workflow.py` (or wherever the `StateGraph` is assembled) — not just from the UI rendering layer. A UI-only removal would leave the backend graph and the displayed graph out of sync, which defeats the entire point of the earlier work that made the UI reflect the real topology via `get_graph_topology()`.
4. **Regenerate any static graph diagram artifact** if one exists in the repo (e.g. a saved `.png`/`.mermaid` export of the graph used in documentation or the README) using the same introspection method originally used to generate it (`get_graph().draw_mermaid_png()` or equivalent), so it reflects the new, pruned topology. If no such static asset exists in the repo, skip this — don't create one that wasn't there before.
5. Confirm the live UI graph canvas (which reads topology dynamically) automatically reflects the pruned graph without any separate UI-side edit — if it doesn't update automatically, that itself indicates the UI topology source isn't actually reading from the live backend graph, which would be a regression from earlier work and needs to be flagged, not worked around.

### Verification before reporting this phase complete
- [ ] You have a clear, evidenced answer for whether the `auto_resolve` edge and `investigation_summary` node are actually reachable/used, based on tracing the routing/node code — not a guess.
- [ ] If removed: the backend graph, the live UI graph canvas, and any static diagram asset are all consistent with each other post-removal.
- [ ] If NOT removed (because you found real usage): you've reported back exactly what condition/logic uses them, so we can decide together rather than you unilaterally keeping or cutting them.
- [ ] Run at least one full incident end-to-end after this change and confirm the graph still executes correctly with no broken edges/orphaned nodes.

---

Start with Phase 1 now. Stop and ask before moving to Phase 2, Phase 3, Phase 4, and Phase 5 in turn.
