"""Tests du seeding Neo4j : compte de noeuds et relations."""
from __future__ import annotations

import pytest

from graph.graph_client import Neo4jClient
from graph.ingestion.run_all import run_all


@pytest.fixture(scope="module")
def seeded_graph():
    """Seed le graphe une fois pour le module de tests."""
    try:
        with Neo4jClient() as client:
            client.verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j non disponible pour les tests : {exc}")

    run_all()
    return True


def test_graph_has_clients(seeded_graph):
    with Neo4jClient() as client:
        result = client.run("MATCH (c:Client) RETURN count(c) AS n")
    assert result[0]["n"] >= 5


def test_graph_has_products(seeded_graph):
    with Neo4jClient() as client:
        result = client.run("MATCH (p:Product) RETURN count(p) AS n")
    assert result[0]["n"] >= 5


def test_graph_has_orders(seeded_graph):
    with Neo4jClient() as client:
        result = client.run("MATCH (o:Order) RETURN count(o) AS n")
    assert result[0]["n"] >= 4


def test_graph_has_logs(seeded_graph):
    with Neo4jClient() as client:
        result = client.run("MATCH (l:LogEvent) RETURN count(l) AS n")
    assert result[0]["n"] >= 10


def test_graph_has_tickets_with_embeddings(seeded_graph):
    with Neo4jClient() as client:
        result = client.run(
            "MATCH (t:Ticket) WHERE t.embedding IS NOT NULL RETURN count(t) AS n"
        )
    assert result[0]["n"] >= 5


def test_graph_has_ticket_product_links(seeded_graph):
    with Neo4jClient() as client:
        result = client.run(
            "MATCH (:Ticket)-[:RELATED_TO_PRODUCT]->(:Product) RETURN count(*) AS n"
        )
    assert result[0]["n"] >= 5
