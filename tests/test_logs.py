"""Tests de l'investigateur de logs."""
from sub_agents.logs_investigator.agent import LogsInvestigatorAgent
from shared.state import GraphState, ParsedIncident


def test_logs_finds_errors_for_service():
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(service_id="svc-fiber-12345").model_dump(),
    )
    result = LogsInvestigatorAgent().run(state)
    logs = result["logs"]
    assert logs["has_clear_signal"] is True
    assert any("log-001" in lid for lid in logs["source_ids"])


def test_logs_no_match():
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(service_id="svc-unknown").model_dump(),
    )
    result = LogsInvestigatorAgent().run(state)
    logs = result["logs"]
    assert logs["relevant_logs"] == []
    assert logs["has_clear_signal"] is False
