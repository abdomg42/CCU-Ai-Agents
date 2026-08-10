"""Ingestion des commandes TMF622 depuis mocks/mock_orders_tmf622.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import get_settings
from graph.graph_client import Neo4jClient

logger = logging.getLogger(__name__)


def ingest_orders(orders_path: Path | None = None) -> dict[str, int]:
    """Crée/MERGE les commandes et les relie au client et au produit."""
    settings = get_settings()
    orders_path = orders_path or settings.MOCK_ORDERS

    with open(orders_path, encoding="utf-8") as f:
        orders = json.load(f)

    # Neo4j n'accepte pas les propriétés imbriquées (Map) : on sérialise les caractéristiques en JSON.
    for order in orders:
        if "characteristics" in order and order["characteristics"] is not None:
            order["characteristics_json"] = json.dumps(order["characteristics"], ensure_ascii=False)
        else:
            order["characteristics_json"] = "{}"

    cypher = """
    UNWIND $orders AS order
    MERGE (o:Order {id: order.order_id})
    SET o.status = order.status,
        o.reason = order.reason,
        o.characteristics = order.characteristics_json
    WITH o, order
    MERGE (c:Client {id: order.customer_id})
    MERGE (c)-[:PLACED_ORDER]->(o)
    WITH o, c, order
    MERGE (p:Product {name: order.product})
    SET p.type = CASE
        WHEN order.product CONTAINS 'Fibre' THEN 'fiber'
        WHEN order.product CONTAINS 'Mobile' THEN 'mobile'
        WHEN order.product CONTAINS 'SIM' THEN 'sim'
        WHEN order.product CONTAINS 'LAN' THEN 'lan'
        WHEN order.product CONTAINS 'Voice' THEN 'billing'
        ELSE 'unknown'
    END
    MERGE (o)-[:FOR_PRODUCT]->(p)
    WITH o, c, p, order
    OPTIONAL MATCH (s:Subscription {service_id: order.service_id})
    FOREACH (_ IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
        MERGE (o)-[:FOR_SERVICE]->(s)
    )
    RETURN count(DISTINCT o) AS orders_created,
           count(DISTINCT c) AS clients_linked,
           count(DISTINCT p) AS products_linked,
           count(DISTINCT s) AS services_linked
    """

    with Neo4jClient() as client:
        result = client.write(cypher, {"orders": orders})
        counts = result[0] if result else {}

    logger.info(
        "Commandes ingérées : %s commandes, %s clients, %s produits, %s services liés",
        counts.get("orders_created", 0),
        counts.get("clients_linked", 0),
        counts.get("products_linked", 0),
        counts.get("services_linked", 0),
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ingest_orders()
