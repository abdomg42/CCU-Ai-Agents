"""Seed Zammad with tickets created from CRM/Postgres clients.

Usage:
    python infra/scripts/seed_zammad_from_crm.py
    python infra/scripts/seed_zammad_from_crm.py --count 10
    python infra/scripts/seed_zammad_from_crm.py --source neo4j

The script reads clients from Postgres (default) or Neo4j and creates tickets
in Zammad with realistic titles/descriptions based on contract/tenure/churn.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ticketing import get_ticketing_backend

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _fetch_clients_from_postgres(limit: int) -> list[dict[str, Any]]:
    from tools.crm_client import PostgresCRMClient

    with PostgresCRMClient() as client:
        cur = client._conn.cursor()
        cur.execute(
            "SELECT id, tenure, contract, monthly_charges, total_charges, churn FROM clients LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "id": row[0],
            "tenure": row[1],
            "contract": row[2],
            "monthly_charges": row[3],
            "total_charges": row[4],
            "churn": row[5],
        }
        for row in rows
    ]


def _fetch_clients_from_neo4j(limit: int) -> list[dict[str, Any]]:
    from graph.graph_client import Neo4jClient

    with Neo4jClient() as client:
        result = client.run(
            "MATCH (c:Client) RETURN c.id AS id LIMIT $limit",
            {"limit": limit},
        )
    return [{"id": row["id"]} for row in result]


def _build_ticket(client: dict[str, Any]) -> dict[str, Any]:
    """Génère un ticket réaliste à partir des données client."""
    client_id = client["id"]
    contract = str(client.get("contract", "")).lower()
    churn = str(client.get("churn", "")).lower()
    tenure = int(client.get("tenure") or 0)
    monthly = float(client.get("monthly_charges") or 0)

    # Email client fictif normalisé pour Zammad.
    customer_email = f"{client_id.lower()}@ccu.local"

    if churn == "yes":
        title = "Client churn - demande de rétention"
        body = (
            f"Client {client_id} a résilié son abonnement. "
            f"Ancien contrat : {contract}. Ancienneté : {tenure} mois. "
            "Action : contacter le client pour une offre de rétention."
        )
        priority = "2 normal"
    elif "month" in contract and monthly > 80:
        title = "Écart de facturation - client haut débit"
        body = (
            f"Client {client_id} signale un montant inhabituel de {monthly} € sur sa facture. "
            f"Contrat {contract}, {tenure} mois d'ancienneté. Vérifier les charges récurrentes."
        )
        priority = "1 low"
    elif tenure > 60:
        title = "Demande de remise fidélité"
        body = (
            f"Client {client_id} ({tenure} mois d'ancienneté) demande une remise fidélité. "
            f"Contrat {contract}. Vérifier les offres disponibles."
        )
        priority = "1 low"
    else:
        title = "Question technique sur contrat"
        body = (
            f"Client {client_id} demande une clarification sur son contrat ({contract}). "
            f"Ancienneté : {tenure} mois."
        )
        priority = "3 high"

    return {
        "title": title,
        "body": body,
        "customer": customer_email,
        "priority": priority,
    }


def _create_tickets(tickets: list[dict[str, Any]]) -> int:
    backend = get_ticketing_backend()
    success = 0
    for ticket in tickets:
        try:
            backend.create_ticket(
                title=ticket["title"],
                body=ticket["body"],
                customer=ticket["customer"],
                priority=ticket["priority"],
            )
            success += 1
            logger.info("Ticket créé : %s", ticket["title"])
        except Exception as exc:
            logger.warning("Échec création ticket %s : %s", ticket["title"], exc)
    return success


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed Zammad with CRM-based tickets")
    parser.add_argument("--count", type=int, default=20, help="Number of tickets to create")
    parser.add_argument("--source", choices=["postgres", "neo4j"], default="postgres", help="CRM source")
    args = parser.parse_args()

    if args.source == "postgres":
        clients = _fetch_clients_from_postgres(args.count)
    else:
        clients = _fetch_clients_from_neo4j(args.count)

    logger.info("Fetched %s clients from %s", len(clients), args.source)

    tickets = [_build_ticket(client) for client in clients]
    success = _create_tickets(tickets)

    logger.info("Successfully created %s/%s tickets in Zammad.", success, len(tickets))


if __name__ == "__main__":
    main()
