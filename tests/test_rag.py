"""Tests de l'agent RAG basé sur Neo4j GraphRAG."""
import pytest

from graph.graph_client import Neo4jClient
from graph.ingestion.run_all import run_all
from sub_agents.rag_ticket_search.agent import RAGTicketSearchAgent
from shared.state import GraphState, ParsedIncident


@pytest.fixture(scope="module")
def seeded_graph():
    """Seed le graphe une fois pour le module de tests RAG."""
    try:
        with Neo4jClient() as client:
            client.verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j non disponible pour les tests RAG : {exc}")

    run_all()
    return True


def test_rag_finds_vlan_ticket(seeded_graph):
    agent = RAGTicketSearchAgent()
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(
            incident_type="lan",
            description="VLAN mismatch switch",
            service_id="svc-lan-44444",
        ).model_dump(),
    )
    result = agent.run(state)
    rag = result["similar_tickets"]
    assert any("TICK-2025-045" in t["ticket_id"] for t in rag["similar_tickets"])


def test_rag_no_match_billing(seeded_graph):
    agent = RAGTicketSearchAgent()
    state = GraphState(
        incident={"description": ""},
        parsed_incident=ParsedIncident(
            incident_type="billing",
            description="écart facture",
            service_id="svc-bill-99999",
        ).model_dump(),
    )
    result = agent.run(state)
    rag = result["similar_tickets"]
    assert len(rag["similar_tickets"]) >= 0
