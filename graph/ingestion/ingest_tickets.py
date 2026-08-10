"""Ingestion des tickets historiques résolus depuis mocks/mock_tickets/*.json."""
from __future__ import annotations

import glob
import json
import logging
from pathlib import Path

from config.settings import get_settings
from graph.graph_client import Neo4jClient

logger = logging.getLogger(__name__)


# Mapping heuristique tags -> produit pour les mocks.
# Les vrais tickets réels auront un service_id/order_id explicite.
_TAG_TO_PRODUCT = {
    "fiber": "Fibre Pro 500",
    "olt": "Fibre Pro 500",
    "pon": "Fibre Pro 500",
    "lan": "LAN Pro VPN",
    "vlan": "LAN Pro VPN",
    "switch": "LAN Pro VPN",
    "misconfiguration": "LAN Pro VPN",
    "sim": "Forfait Nano SIM",
    "hss": "Forfait Nano SIM",
    "hlr": "Forfait Nano SIM",
    "iccid": "Forfait Nano SIM",
    "imsi": "Forfait Nano SIM",
    "mobile": "Mobile 5G Enterprise",
    "tmf622": "Mobile 5G Enterprise",
    "crm": "Mobile 5G Enterprise",
    "timeout": "Mobile 5G Enterprise",
    "acknowledged": "Mobile 5G Enterprise",
    "billing": "Cloud Voice",
    "écart": "Cloud Voice",
    "indéterminé": "Cloud Voice",
}


def _infer_product(ticket: dict) -> str | None:
    tags = {t.lower() for t in ticket.get("tags", [])}
    for tag, product in _TAG_TO_PRODUCT.items():
        if tag in tags:
            return product
    # Fallback sur les mots-clés du résumé / description
    text = f"{ticket.get('summary', '')} {ticket.get('description', '')}".lower()
    for tag, product in _TAG_TO_PRODUCT.items():
        if tag in text:
            return product
    return None


def ingest_tickets(tickets_dir: Path | None = None) -> dict[str, int]:
    """Crée/MERGE les tickets résolus et les relie au produit concerné."""
    settings = get_settings()
    tickets_dir = tickets_dir or settings.MOCK_TICKETS_DIR

    tickets = []
    for path in glob.glob(str(tickets_dir / "*.json")):
        with open(path, encoding="utf-8") as f:
            ticket = json.load(f)
            ticket["product_name"] = _infer_product(ticket)
            tickets.append(ticket)

    cypher = """
    UNWIND $tickets AS ticket
    MERGE (t:Ticket {id: ticket.ticket_id})
    SET t.summary = ticket.summary,
        t.description = ticket.description,
        t.root_cause = ticket.root_cause,
        t.resolution = ticket.resolution,
        t.tags = ticket.tags,
        t.status = 'resolved'
    WITH t, ticket
    OPTIONAL MATCH (p:Product {name: ticket.product_name})
    FOREACH (_ IN CASE WHEN p IS NOT NULL THEN [1] ELSE [] END |
        MERGE (t)-[:RELATED_TO_PRODUCT]->(p)
    )
    WITH t, p
    RETURN count(DISTINCT t) AS tickets_created,
           count(DISTINCT p) AS products_linked
    """

    with Neo4jClient() as client:
        result = client.write(cypher, {"tickets": tickets})
        counts = result[0] if result else {}

    logger.info(
        "Tickets ingérés : %s tickets, %s produits liés",
        counts.get("tickets_created", 0),
        counts.get("products_linked", 0),
    )
    return counts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    ingest_tickets()
