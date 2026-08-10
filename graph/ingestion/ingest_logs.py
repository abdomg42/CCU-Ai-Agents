"""Ingestion des logs réseau depuis mocks/mock_logs.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import get_settings
from graph.graph_client import Neo4jClient

logger = logging.getLogger(__name__)


def ingest_logs(logs_path: Path | None = None) -> dict[str, int]:
    """Crée/MERGE les événements de log et les relie aux commandes/services."""
    settings = get_settings()
    logs_path = logs_path or settings.MOCK_LOGS

    with open(logs_path, encoding="utf-8") as f:
        logs = json.load(f)

    cypher = """
    UNWIND $logs AS log
    MERGE (l:LogEvent {id: log.log_id})
    SET l.timestamp = log.timestamp,
        l.severity = log.severity,
        l.source = log.source,
        l.message = log.message,
        l.service_id = log.service_id,
        l.order_id = log.order_id
    WITH l, log
    OPTIONAL MATCH (o:Order {id: log.order_id})
    FOREACH (_ IN CASE WHEN o IS NOT NULL THEN [1] ELSE [] END |
        MERGE (l)-[:BELONGS_TO_ORDER]->(o)
    )
    WITH l, log, o
    OPTIONAL MATCH (s:Subscription {service_id: log.service_id})
    FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
        MERGE (l)-[:BELONGS_TO_SERVICE]->(s)
    )
    RETURN count(DISTINCT l) AS logs_created,
           count(DISTINCT o) AS orders_linked,
           count(DISTINCT s) AS services_linked
    """

    with Neo4jClient() as client:
        result = client.write(cypher, {"logs": logs})
        counts = result[0] if result else {}

    logger.info(
        "Logs ingérés : %s logs, %s commandes, %s services liés",
        counts.get("logs_created", 0),
        counts.get("orders_linked", 0),
        counts.get("services_linked", 0),
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ingest_logs()
