"""Vectorise les descriptions des tickets historiques et persiste les embeddings dans Neo4j."""
from __future__ import annotations

import logging

from graph.graph_client import Neo4jClient
from graph.embedding_provider import get_embedding_provider

logger = logging.getLogger(__name__)


def generate_embeddings(batch_size: int = 32) -> dict[str, int]:
    """Calcule et stocke les embeddings pour tous les tickets n'en ayant pas encore."""
    provider = get_embedding_provider()

    select_cypher = """
    MATCH (t:Ticket)
    WHERE t.embedding IS NULL AND t.description IS NOT NULL
    RETURN t.id AS id, t.description AS description
    """

    update_cypher = """
    UNWIND $rows AS row
    MATCH (t:Ticket {id: row.id})
    SET t.embedding = row.embedding
    RETURN count(*) AS updated
    """

    with Neo4jClient() as client:
        rows = client.run(select_cypher)

    if not rows:
        logger.info("Aucun ticket à vectoriser.")
        return {"updated": 0, "batches": 0}

    total_updated = 0
    batches = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [r["description"] for r in batch]
        vectors = provider.embed(texts)
        update_rows = [
            {"id": r["id"], "embedding": vector}
            for r, vector in zip(batch, vectors)
        ]
        with Neo4jClient() as client:
            result = client.write(update_cypher, {"rows": update_rows})
            total_updated += result[0].get("updated", 0) if result else 0
            batches += 1

    logger.info("Embeddings générés : %s tickets mis à jour en %s lots", total_updated, batches)
    return {"updated": total_updated, "batches": batches}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    generate_embeddings()
