"""Tests de l'agent root cause."""
from sub_agents.root_cause_reasoner.agent import RootCauseReasonerAgent
from shared.state import GraphState, ParsedIncident


def test_root_cause_with_sources():
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(incident_type="lan").model_dump(),
        logs={"source_ids": ["log-008"], "summary": "VLAN mismatch", "has_clear_signal": True},
        customer_context={"source_ids": ["acc-44444", "ord-2026-004"], "risk_factors": []},
        similar_tickets={
            "source_ids": ["TICK-2025-045"],
            "similar_tickets": [{
                "ticket_id": "TICK-2025-045",
                "root_cause": "VLAN mismatch entre service et port switch",
                "distance": 0.1,
            }],
            "synthesis": "VLAN",
        },
    )
    result = RootCauseReasonerAgent().run(state)
    rc = result["root_cause"]
    assert rc["cause"] == "VLAN mismatch entre service et port switch"
    assert rc["confidence"] == "forte"
    assert "TICK-2025-045" in rc["source_ids"]


def test_root_cause_refuses_hallucination():
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(incident_type="billing").model_dump(),
        logs={"source_ids": [], "summary": "", "has_clear_signal": False},
        customer_context={"source_ids": [], "risk_factors": []},
        similar_tickets={"source_ids": [], "similar_tickets": [], "synthesis": ""},
    )
    result = RootCauseReasonerAgent().run(state)
    rc = result["root_cause"]
    assert rc["cause"] == "indéterminée"
    assert rc["confidence"] == "faible"
    assert rc["source_ids"] == []
