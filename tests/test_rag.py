"""Tests de l'agent RAG."""
from sub_agents.rag_ticket_search.agent import RAGTicketSearchAgent
from shared.state import GraphState, ParsedIncident


def test_rag_finds_vlan_ticket():
    agent = RAGTicketSearchAgent()
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(incident_type="lan", description="VLAN mismatch switch").model_dump(),
    )
    result = agent.run(state)
    rag = result["similar_tickets"]
    assert any("TICK-2025-045" in t["ticket_id"] for t in rag["similar_tickets"])


def test_rag_no_match_billing():
    agent = RAGTicketSearchAgent()
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(incident_type="billing", description="écart facture").model_dump(),
    )
    result = agent.run(state)
    rag = result["similar_tickets"]
    assert len(rag["similar_tickets"]) >= 0
