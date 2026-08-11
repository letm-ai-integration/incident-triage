"""Classification Agent: incident category + priority.

Priority is never LLM-only: app/rules/classification.py computes a
deterministic floor first, and the LLM's classification may escalate above
it but is never allowed to fall below it.
"""
from __future__ import annotations

from app.agents.classification.parser import parse_classification_response
from app.agents.classification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.llm.client import create_structured_agent
from app.rules.classification import compute_rule_based_priority, most_urgent


def classify_incident(incident: Incident, model: str | None = None) -> ClassificationResult:
    """Classify ``incident`` into a category + priority.

    Computes the deterministic rule floor first, asks the LLM to classify
    against that floor, then reconciles the two before returning.
    """
    rule_priority = compute_rule_based_priority(incident)
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=ClassificationResult,
        model=model,
    )
    response = agent.invoke(
        {
            "messages": [
                {"role": "user", "content": build_user_prompt(incident, rule_priority)}
            ]
        }
    )
    llm_result = parse_classification_response(response)
    return _reconcile_with_rule_floor(llm_result, rule_priority)


def _reconcile_with_rule_floor(
    llm_result: ClassificationResult, rule_priority: Priority
) -> ClassificationResult:
    agrees = llm_result.priority == rule_priority
    final_priority = most_urgent(llm_result.priority, rule_priority)
    return llm_result.model_copy(
        update={
            "priority": final_priority,
            "rule_based_priority": rule_priority,
            "agrees_with_rule": agrees,
        }
    )
