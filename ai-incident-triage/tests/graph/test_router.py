"""Pure routing-function tests -- see app/graph/router.py's module docstring
for the rule that these must only inspect state, never call services.
"""
from app.graph.router import route_after_ingestion


def test_route_after_ingestion_quarantine():
    assert route_after_ingestion({"quarantined": True}) == "quarantine"


def test_route_after_ingestion_continue():
    assert route_after_ingestion({"quarantined": False}) == "continue"


def test_route_after_ingestion_defaults_to_continue_when_unset():
    assert route_after_ingestion({}) == "continue"
