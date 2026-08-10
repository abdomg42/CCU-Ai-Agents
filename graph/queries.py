"""Requêtes Cypher paramétrées pour le GraphRAG sur tickets historiques."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import get_settings
from graph.graph_client import Neo4jClient
from graph.embedding_provider import get_embedding_provider


@dataclass
class SimilarIncidentResult:
    """Résultat d'une recherche GraphRAG de tickets similaires."""

    ticket_id: str
    summary: str
    description: str
    root_cause: str
    resolution: str
    score: float


def search_similar_incidents(
    incident_id: str,
    query_text: str,
    top_k: int = 5,
) -> list[SimilarIncidentResult]:
    """Recherche vectorielle filtrée par proximité de graphe (même produit / même commande).

    Args:
        incident_id: service_id, order_id ou customer_id de l'incident courant.
        query_text: texte à vectoriser pour la recherche.
        top_k: nombre maximum de résultats retournés.

    Returns:
        Liste de tickets historiques dont le score de similarité cosine est >= seuil.
    """
    settings = get_settings()
    provider = get_embedding_provider(settings)
    query_embedding = provider.embed([query_text])[0]

    cypher = """
    // 1. Identifier le(s) produit(s) liés à l'ancre (service, commande ou client)
    OPTIONAL MATCH (anchor)
    WHERE anchor.service_id = $incident_id OR anchor.id = $incident_id
    WITH anchor
    OPTIONAL MATCH (anchor)-[:SUBSCRIBED_TO]->(prod1:Product)
    OPTIONAL MATCH (anchor)-[:FOR_PRODUCT]->(prod2:Product)
    OPTIONAL MATCH (anchor)-[:HAS_SUBSCRIPTION]->(:Subscription)-[:SUBSCRIBED_TO]->(prod3:Product)
    WITH collect(DISTINCT prod1.name) + collect(DISTINCT prod2.name) + collect(DISTINCT prod3.name) AS product_names

    // 2. Recherche vectorielle native Neo4j
    CALL db.index.vector.queryNodes($index_name, $candidate_limit, $query_embedding)
    YIELD node AS t, score
    WHERE score >= $threshold
      // Filtre par proximité de graphe : même produit / même type de commande
      AND (size(product_names) = 0 OR EXISTS {
        MATCH (t)-[:RELATED_TO_PRODUCT]->(p:Product)
        WHERE p.name IN product_names
      })
    RETURN t.id AS ticket_id, t.summary AS summary, t.description AS description,
           t.root_cause AS root_cause, t.resolution AS resolution, score
    ORDER BY score DESC
    LIMIT $top_k
    """

    params: dict[str, Any] = {
        "incident_id": incident_id,
        "query_embedding": query_embedding,
        "index_name": settings.TICKETS_VECTOR_INDEX,
        "candidate_limit": top_k * 5,
        "threshold": settings.VECTOR_SIMILARITY_THRESHOLD,
        "top_k": top_k,
    }

    with Neo4jClient() as client:
        records = client.run(cypher, params)

    return [
        SimilarIncidentResult(
            ticket_id=r["ticket_id"],
            summary=r["summary"],
            description=r["description"],
            root_cause=r["root_cause"],
            resolution=r["resolution"],
            score=r["score"],
        )
        for r in records
    ]


def build_similar_ticket_links(top_k: int = 3, threshold: float | None = None) -> dict[str, int]:
    """Crée les relations :Ticket-[:SIMILAR_TO {score}]->(:Ticket) entre tickets résolus.

    Optionnel : enrichit le graphe pour permettre une traversée de similarité explicite.
    """
    settings = get_settings()
    threshold = threshold or settings.VECTOR_SIMILARITY_THRESHOLD

    # Supprime les anciennes relations SIMILAR_TO pour recalculer proprement
    delete_cypher = """
    MATCH (:Ticket)-[r:SIMILAR_TO]->(:Ticket)
    DELETE r
    """

    build_cypher = """
    MATCH (t:Ticket)
    WHERE t.embedding IS NOT NULL
    WITH t, t.embedding AS embedding
    CALL db.index.vector.queryNodes($index_name, $top_k + 1, embedding)
    YIELD node AS other, score
    WHERE other.id <> t.id AND score >= $threshold
    MERGE (t)-[r:SIMILAR_TO]->(other)
    SET r.score = score
    RETURN count(r) AS relationships_created
    """

    with Neo4jClient() as client:
        client.write(delete_cypher)
        result = client.write(build_cypher, {"index_name": settings.TICKETS_VECTOR_INDEX, "top_k": top_k, "threshold": threshold})

    return {"relationships_created": result[0].get("relationships_created", 0) if result else 0}
