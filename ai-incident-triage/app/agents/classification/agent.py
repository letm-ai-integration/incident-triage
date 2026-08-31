"""Classification Agent: incident category + priority.

Priority is never LLM-only: app/rules/classification.py computes a
deterministic floor first, and the LLM's classification may escalate above
it but is never allowed to fall below it.
"""
from __future__ import annotations

import logging

from app.agents.classification.parser import parse_classification_response
from app.agents.classification.prompt import SYSTEM_PROMPT, build_user_prompt
from app.domain.enums.priority import Priority
from app.domain.models.classification import ClassificationResult
from app.domain.models.incident import Incident
from app.llm.client import create_structured_agent
from app.logging_utils import agent_entry, agent_output, agent_exit, agent_error
from app.rules.classification import compute_rule_based_priority, most_urgent

logger = logging.getLogger(__name__)


def classify_incident(incident: Incident, model: str | None = None) -> ClassificationResult:
    """Classify ``incident`` into a category + priority.

    Computes the deterministic rule floor first, asks the LLM to classify
    against that floor, then reconciles the two before returning.
    """
    agent_entry("ClassificationAgent", f"incident={incident.incident_id}")
    rule_priority = compute_rule_based_priority(incident)
    logger.info("[classification.agent] rule floor priority=%s incident=%s", rule_priority.value, incident.incident_id)
    agent = create_structured_agent(
        system_prompt=SYSTEM_PROMPT,
        output_schema=ClassificationResult,
        model=model,
    )
    logger.info("[classification.agent] invoking LLM (model=%s)...", model or "provider-default")
    try:
        response = agent.invoke(
            {
                "messages": [
                    {"role": "user", "content": build_user_prompt(incident, rule_priority)}
                ]
            }
        )
    except Exception:
        agent_error("ClassificationAgent", Exception("LLM invocation failed"), f"incident={incident.incident_id}")
        logger.exception(
            "[classification.agent] LLM invocation failed -- check provider base_url "
            "reachability, API key, and network/proxy settings"
        )
        raise
    logger.info("[classification.agent] LLM invocation succeeded")
    llm_result = parse_classification_response(response)
    result = _reconcile_with_rule_floor(llm_result, rule_priority)
    agent_output(
        "ClassificationAgent",
        f"type={result.incident_type.value} priority={result.priority.value} "
        f"confidence={result.confidence:.2f} agrees_with_rule={result.agrees_with_rule}",
    )
    agent_exit("ClassificationAgent")
    return result


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
