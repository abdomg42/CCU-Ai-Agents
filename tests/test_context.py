"""Tests de l'agent contexte client."""
from sub_agents.context_agent.agent import ContextAgent
from shared.state import GraphState, ParsedIncident


def test_context_finds_customer_and_order():
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(service_id="svc-mobile-98765").model_dump(),
    )
    result = ContextAgent().run(state)
    ctx = result["customer_context"]
    assert ctx["customer_id"] == "acc-56789"
    assert ctx["order"]["order_id"] == "ord-2026-002"
    assert any("acknowledged" in f for f in ctx["risk_factors"])


def test_context_unknown_service():
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(service_id="svc-unknown").model_dump(),
    )
    result = ContextAgent().run(state)
    ctx = result["customer_context"]
    assert ctx["customer_id"] is None
    assert ctx["risk_factors"] == []
