"""Télécharge le dataset ServiceNow synthétique et génère des tickets TMF621.

Usage:
    python scripts/seed/generate_tickets.py --output mocks/mock_tickets --count 50
    python scripts/seed/generate_tickets.py --output mocks/mock_tickets --count 50 --push-to-zammad
"""
from __future__ import annotations

import argparse
import json
import logging
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Permet d'exécuter le script depuis scripts/seed/ sans PYTHONPATH.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from datasets import load_dataset

from config.settings import get_settings
from tools.ticketing_client import push_ticket_to_zammad

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


# Mapping heuristique des colonnes courantes du dataset synthetic-servicenow-incidents
COLUMN_ALIASES = {
    "ticket_id": ["number", "ticket_id", "incident_number", "sys_id", "id"],
    "summary": ["short_description", "summary", "title", "subject"],
    "description": ["description", "detailed_description", "work_notes", "notes"],
    "priority": ["priority", "urgency"],
    "status": ["state", "status", "incident_state"],
    "category": ["category", "cmdb_ci", "subcategory"],
    "root_cause": ["root_cause", "cause", "resolution_code", "close_code"],
    "resolution": ["resolution", "resolution_notes", "close_notes", "work_notes"],
}


def _pick(field: str, row: dict[str, Any]) -> Any:
    """Retourne la première colonne disponible correspondant à un champ attendu."""
    for alias in COLUMN_ALIASES.get(field, [field]):
        if alias in row and row[alias] is not None:
            return row[alias]
    return None


_SERVICE_NOW_PRIORITY_MAP = {
    "1 - Critical": "P1",
    "2 - High": "P2",
    "3 - Moderate": "P3",
    "4 - Low": "P4",
    "1": "P1",
    "2": "P2",
    "3": "P3",
    "4": "P4",
    "critical": "P1",
    "high": "P2",
    "moderate": "P3",
    "low": "P4",
}


def _to_priority(raw: Any) -> str:
    if raw is None:
        return "P3"
    key = str(raw).strip().lower()
    return _SERVICE_NOW_PRIORITY_MAP.get(key, "P3")


def _to_tags(row: dict[str, Any], category: str | None) -> list[str]:
    tags: set[str] = set()
    if category:
        tags.add(category.lower().replace(" ", "_"))
    text = " ".join(str(v) for v in row.values() if isinstance(v, str)).lower()
    keywords = {
        "fiber": "fiber",
        "fibre": "fiber",
        "olt": "olt",
        "pon": "pon",
        "sim": "sim",
        "hss": "hss",
        "hlr": "hlr",
        "iccid": "iccid",
        "mobile": "mobile",
        "crm": "crm",
        "billing": "billing",
        "vlan": "vlan",
        "switch": "switch",
        "lan": "lan",
        "provisioning": "provisioning",
    }
    for keyword, tag in keywords.items():
        if keyword in text:
            tags.add(tag)
    return sorted(tags) if tags else ["general"]


def _to_snake(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()[:50]


def _sanitize(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool, list, dict)):
        return value
    return str(value)


def _transform_row(row: dict[str, Any]) -> dict[str, Any]:
    """Transforme une ligne du dataset en ticket TMF621/CCU."""
    ticket_id = _pick("ticket_id", row) or f"TICK-HF-{random.randint(100000, 999999)}"
    summary = str(_pick("summary", row) or "No summary")
    description = str(_pick("description", row) or summary)
    priority = _to_priority(_pick("priority", row))
    status = str(_pick("status", row) or "new")
    category = str(_pick("category", row) or "general")
    root_cause = str(_pick("root_cause", row) or "undetermined")
    resolution = str(_pick("resolution", row) or "")
    tags = _to_tags(row, category)

    created_at = datetime.now(timezone.utc).isoformat()

    return {
        "ticket_id": str(ticket_id).replace(" ", "_"),
        "summary": summary,
        "description": description,
        "root_cause": root_cause,
        "resolution": resolution,
        "tags": tags,
        "priority": priority,
        "status": status,
        "category": category,
        "created_at": created_at,
        # TMF621 Trouble Ticket structure
        "tmf621": {
            "id": str(ticket_id).replace(" ", "_"),
            "href": f"/tmf621/troubleTicket/{str(ticket_id).replace(' ', '_')}",
            "creationDate": created_at,
            "description": summary,
            "severity": priority,
            "priority": priority,
            "status": status,
            "type": category,
        },
    }


def generate(
    output_dir: Path,
    count: int = 50,
    push_to_zammad: bool = False,
    max_retries: int = 3,
) -> list[Path]:
    """Télécharge le dataset, transforme les tickets et les sauvegarde."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Téléchargement du dataset 6StringNinja/synthetic-servicenow-incidents...")
    ds = load_dataset("6StringNinja/synthetic-servicenow-incidents", split="train")
    total = len(ds)
    sample_count = min(count, total)
    indices = random.sample(range(total), sample_count)

    created: list[Path] = []
    for idx in indices:
        row = {k: _sanitize(v) for k, v in dict(ds[idx]).items()}
        ticket = _transform_row(row)
        path = output_dir / f"{ticket['ticket_id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(ticket, f, indent=2, ensure_ascii=False)
        created.append(path)

        if push_to_zammad:
            zammad_ticket = {
                "ticket_id": ticket["ticket_id"],
                "short_description": ticket["summary"],
                "description": ticket["description"],
                "priority": ticket["priority"],
                "category": ticket["category"],
                "status": ticket["status"],
                "root_cause": ticket["root_cause"],
                "resolution_notes": ticket["resolution"],
                "client_id": "nicole.braun@zammad.org",
            }
            for attempt in range(1, max_retries + 1):
                try:
                    push_ticket_to_zammad(zammad_ticket)
                    break
                except Exception as exc:
                    logger.warning(
                        "Échec push Zammad %s (tentative %s/%s): %s",
                        ticket["ticket_id"], attempt, max_retries, exc,
                    )
                    if attempt == max_retries:
                        logger.error("Abandon du push pour %s", ticket["ticket_id"])

    logger.info("%s tickets générés dans %s", len(created), output_dir)
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Génère des tickets depuis ServiceNow synthétique")
    parser.add_argument("--output", default=str(get_settings().MOCK_TICKETS_DIR), help="Dossier de sortie")
    parser.add_argument("--count", type=int, default=50, help="Nombre de tickets à générer")
    parser.add_argument("--push-to-zammad", action="store_true", help="Pousser les tickets dans Zammad")
    parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire")
    args = parser.parse_args()

    random.seed(args.seed)
    generate(
        output_dir=Path(args.output),
        count=args.count,
        push_to_zammad=args.push_to_zammad,
    )
