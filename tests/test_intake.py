"""Tests de l'agent d'intake."""
from sub_agents.intake_parser.agent import IntakeParserAgent
from shared.state import GraphState


def test_intake_extracts_service_and_order():
    state = GraphState(incident={
        "title": "Incident",
        "description": "Le client acc-12345 reporte une coupure sur svc-fiber-12345 pour la commande ord-2026-001.",
    })
    agent = IntakeParserAgent()
    result = agent.run(state)
    parsed = result["parsed_incident"]
    assert parsed["service_id"] == "svc-fiber-12345"
    assert parsed["order_id"] == "ord-2026-001"
    assert parsed["customer_id"] == "acc-12345"
    assert parsed["incident_type"] == "fibre"


def test_intake_empty_description():
    state = GraphState(incident={"title": "", "description": ""})
    result = IntakeParserAgent().run(state)
    parsed = result["parsed_incident"]
    assert parsed["service_id"] is None
    assert parsed["incident_type"] == "autre"
