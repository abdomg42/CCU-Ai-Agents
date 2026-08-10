"""Orchestre le seeding complet du graphe Neo4j à partir des mocks.

Ordre d'exécution :
1. Schéma (contraintes + index vectoriel)
2. Clients / abonnements / produits
3. Commandes TMF622
4. Logs réseau
5. Tickets historiques
6. Génération des embeddings
"""
from __future__ import annotations

import logging
from pathlib import Path

from config.settings import get_settings
from graph.graph_client import Neo4jClient
from graph.ingestion.ingest_clients import ingest_clients
from graph.ingestion.ingest_orders import ingest_orders
from graph.ingestion.ingest_logs import ingest_logs
from graph.ingestion.ingest_tickets import ingest_tickets
from graph.ingestion.generate_embeddings import generate_embeddings
from graph.queries import build_similar_ticket_links

logger = logging.getLogger(__name__)


def _apply_schema(schema_path: Path, vector_dim: int) -> None:
    with open(schema_path, encoding="utf-8") as f:
        cypher = f.read()
    cypher = cypher.replace("__VECTOR_DIM__", str(vector_dim))

    # Sépare les requêtes par point-virgule et exécute les unes après les autres
    statements = [s.strip() for s in cypher.split(";") if s.strip()]
    with Neo4jClient() as client:
        for statement in statements:
            logger.debug("Exécution : %s", statement[:80])
            client.write(statement)


def run_all() -> dict[str, dict]:
    """Lance l'ensemble du seeding et retourne les compteurs."""
    settings = get_settings()
    schema_path = settings.PROJECT_ROOT / "graph" / "schema.cypher"

    logger.info("=== 1. Application du schéma Neo4j ===")
    _apply_schema(schema_path, settings.VECTOR_INDEX_DIM)

    logger.info("=== 2. Ingestion des clients / abonnements / produits ===")
    client_counts = ingest_clients()

    logger.info("=== 3. Ingestion des commandes TMF622 ===")
    order_counts = ingest_orders()

    logger.info("=== 4. Ingestion des logs réseau ===")
    log_counts = ingest_logs()

    logger.info("=== 5. Ingestion des tickets historiques ===")
    ticket_counts = ingest_tickets()

    logger.info("=== 6. Génération des embeddings ===")
    embedding_counts = generate_embeddings()

    logger.info("=== 7. Construction des liens SIMILAR_TO entre tickets ===")
    similar_links = build_similar_ticket_links()

    return {
        "schema": {"applied": True, "vector_dim": settings.VECTOR_INDEX_DIM},
        "clients": client_counts,
        "orders": order_counts,
        "logs": log_counts,
        "tickets": ticket_counts,
        "embeddings": embedding_counts,
        "similar_links": similar_links,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    result = run_all()
    logger.info("Seeding terminé : %s", result)
