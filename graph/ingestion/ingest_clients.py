"""Ingestion des clients et abonnements depuis mocks/mock_crm.json."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from config.settings import get_settings
from graph.graph_client import Neo4jClient

logger = logging.getLogger(__name__)


def ingest_clients(crm_path: Path | None = None) -> dict[str, int]:
    """Crée/MERGE les clients, leurs abonnements et les produits associés."""
    settings = get_settings()
    crm_path = crm_path or settings.MOCK_CRM

    with open(crm_path, encoding="utf-8") as f:
        data = json.load(f)

    customers = data.get("customers", [])

    cypher = """
    UNWIND $customers AS customer
    MERGE (c:Client {id: customer.customer_id})
    SET c.name = customer.name,
        c.segment = customer.segment,
        c.contact = customer.contact,
        c.status = customer.account_status
    WITH c, customer.subscriptions AS subscriptions
    UNWIND subscriptions AS sub
    MERGE (s:Subscription {service_id: sub.service_id})
    SET s.offer = sub.offer,
        s.status = sub.status,
        s.address = sub.address
    MERGE (c)-[:HAS_SUBSCRIPTION]->(s)
    WITH c, s, sub.offer AS offer_name
    MERGE (p:Product {name: offer_name})
    SET p.type = CASE
        WHEN offer_name CONTAINS 'Fibre' THEN 'fiber'
        WHEN offer_name CONTAINS 'Mobile' THEN 'mobile'
        WHEN offer_name CONTAINS 'SIM' THEN 'sim'
        WHEN offer_name CONTAINS 'LAN' THEN 'lan'
        WHEN offer_name CONTAINS 'Voice' THEN 'billing'
        ELSE 'unknown'
    END
    MERGE (s)-[:SUBSCRIBED_TO]->(p)
    RETURN count(DISTINCT c) AS clients_created,
           count(DISTINCT s) AS subscriptions_created,
           count(DISTINCT p) AS products_created
    """

    with Neo4jClient() as client:
        result = client.write(cypher, {"customers": customers})
        counts = result[0] if result else {}

    logger.info(
        "Clients ingérés : %s clients, %s abonnements, %s produits",
        counts.get("clients_created", 0),
        counts.get("subscriptions_created", 0),
        counts.get("products_created", 0),
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ingest_clients()
