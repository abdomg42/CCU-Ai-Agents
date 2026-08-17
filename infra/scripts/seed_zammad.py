"""Injecte les tickets du répertoire mocks/mock_tickets/ dans Zammad.

Usage:
    python infra/scripts/seed_zammad.py
    python infra/scripts/seed_zammad.py --mocks-dir mocks/mock_tickets
"""
from __future__ import annotations

import argparse
import glob
import json
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.ticketing_client import push_ticket_to_zammad

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def _load_ticket(path: Path) -> dict[str, Any] | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Impossible de lire %s: %s", path, exc)
        return None


def _extract_zammad_payload(ticket: dict[str, Any]) -> dict[str, Any]:
    """Convertit un ticket du mock au format attendu par push_ticket_to_zammad."""
    return {
        "ticket_id": ticket.get("ticket_id", ""),
        "short_description": ticket.get("summary", ticket.get("short_description", "")),
        "description": ticket.get("description", ""),
        "priority": ticket.get("priority", "P3"),
        "category": ticket.get("category", "ccu"),
        "status": ticket.get("status", "new"),
        "root_cause": ticket.get("root_cause", ""),
        "resolution_notes": ticket.get("resolution", ticket.get("resolution_notes", "")),
        "client_id": ticket.get("client_id", ticket.get("customer_id", "nicole.braun@zammad.org")),
        "product_type": ticket.get("product_type", ""),
    }


def seed(mocks_dir: Path, max_retries: int = 3) -> None:
    """Pousse tous les tickets JSON du dossier vers Zammad."""
    mocks_dir = Path(mocks_dir)
    if not mocks_dir.exists():
        raise FileNotFoundError(f"Dossier de tickets introuvable : {mocks_dir}")

    paths = sorted(glob.glob(str(mocks_dir / "*.json")))
    logger.info("Injection de %s tickets dans Zammad...", len(paths))

    success = 0
    for path in paths:
        ticket = _load_ticket(Path(path))
        if ticket is None:
            continue

        payload = _extract_zammad_payload(ticket)
        for attempt in range(1, max_retries + 1):
            try:
                push_ticket_to_zammad(payload)
                success += 1
                break
            except Exception as exc:
                logger.warning(
                    "Échec push %s (tentative %s/%s): %s",
                    payload["ticket_id"], attempt, max_retries, exc,
                )
                if attempt == max_retries:
                    logger.error("Abandon du push pour %s", payload["ticket_id"])

    logger.info("Injection terminée : %s/%s tickets poussés.", success, len(paths))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Injecte les tickets mockés dans Zammad")
    parser.add_argument("--mocks-dir", default="mocks/mock_tickets", help="Répertoire contenant les tickets JSON")
    args = parser.parse_args()
    seed(Path(args.mocks_dir))
