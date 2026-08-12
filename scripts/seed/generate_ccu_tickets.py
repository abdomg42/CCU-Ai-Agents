"""Génère 30 tickets CCU synthétiques via l'API Anthropic.

Usage:
    python scripts/seed/generate_ccu_tickets.py --output mocks/mock_tickets --count 30
    python scripts/seed/generate_ccu_tickets.py --output mocks/mock_tickets --count 30 --push-to-zammad
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

import httpx

from config.settings import get_settings
from tools.ticketing_client import push_ticket_to_zammad

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    'Generate realistic technical incident tickets for a telecom '
    'Product Ordering system (TMF620/622). Each ticket must follow this '
    'JSON schema: ticket_id, client_id, order_id (nullable), product_type, '
    'short_description, description, priority, category, created_at, '
    'status, root_cause, resolution_notes, related_log_pattern. Vary '
    'cases across network failures, provisioning failures, CRM sync '
    'issues, double billing, and catalog eligibility conflicts. Include '
    'at least 3 tickets with root_cause="undetermined". Respond with a '
    'JSON array only.'
)

REQUIRED_FIELDS = [
    "ticket_id",
    "client_id",
    "order_id",
    "product_type",
    "short_description",
    "description",
    "priority",
    "category",
    "created_at",
    "status",
    "root_cause",
    "resolution_notes",
    "related_log_pattern",
]

CCU_CATEGORIES = [
    "network",
    "provisioning",
    "billing",
    "crm_sync",
    "catalog_eligibility",
]

CCU_PRODUCTS = [
    "Mobile 5G Enterprise",
    "Fibre Pro 500",
    "LAN Pro VPN",
    "Forfait Nano SIM",
    "Cloud Voice",
]


def _generate_with_anthropic(
    api_key: str, model: str, count: int, timeout: float = 120.0
) -> list[dict[str, Any]]:
    """Appelle l'API Anthropic Messages et retourne la liste de tickets."""
    user_content = f"Generate exactly {count} tickets. No extra text."
    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "max_tokens": 4096,
            "temperature": 0.8,
            "system": SYSTEM_PROMPT,
            "messages": [{"role": "user", "content": user_content}],
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()

    content = data.get("content", [])
    text = ""
    for block in content:
        if block.get("type") == "text":
            text += block.get("text", "")

    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    return json.loads(text)


def _generate_local_fallback(count: int) -> list[dict[str, Any]]:
    """Tickets déterministes si Anthropic n'est pas disponible."""
    templates = [
        {
            "product_type": "Fibre Pro 500",
            "category": "network",
            "short_description": "Fiber signal loss on OLT North",
            "description": "Customer reports total Internet outage. OLT logs show RX power below -28 dBm on the PON port.",
            "priority": "P2",
            "root_cause": "Perte de signal fibre optique",
            "resolution_notes": "Technician re-terminated fiber at the PTO.",
            "related_log_pattern": "OLT_RX_POWER_LOW pon-port=3/1/7",
        },
        {
            "product_type": "Mobile 5G Enterprise",
            "category": "crm_sync",
            "short_description": "Order stuck in CRM acknowledged state",
            "description": "Order remains in 'acknowledged' for 45 minutes; downstream provisioning cannot start.",
            "priority": "P2",
            "root_cause": "Timeout CRM lors de la récupération du profil client",
            "resolution_notes": "CRM profile retried and order moved to inProgress.",
            "related_log_pattern": "CRM_API_TIMEOUT order_id={order_id} duration=45000ms",
        },
        {
            "product_type": "Forfait Nano SIM",
            "category": "provisioning",
            "short_description": "SIM ICCID not provisioned in HLR",
            "description": "New SIM activation fails with HSS 'Unknown subscriber' response.",
            "priority": "P2",
            "root_cause": "ICCID SIM non provisionnée dans le HLR",
            "resolution_notes": "Reprovisioned ICCID in HLR and resent activation request.",
            "related_log_pattern": "HSS_UNKNOWN_SUBSCRIBER imsi={client_id} iccid=",
        },
        {
            "product_type": "LAN Pro VPN",
            "category": "network",
            "short_description": "VLAN mismatch on switch port",
            "description": "CE switch reports VLAN mismatch for the ordered LAN service.",
            "priority": "P3",
            "root_cause": "VLAN mismatch entre service et port switch",
            "resolution_notes": "Corrected VLAN configuration on the switch port.",
            "related_log_pattern": "SWITCH_VLAN_MISMATCH port=Gi0/24 expected=200 actual=300",
        },
        {
            "product_type": "Cloud Voice",
            "category": "billing",
            "short_description": "Double billing for Cloud Voice subscription",
            "description": "Customer invoiced twice for the same Cloud Voice subscription in this billing cycle.",
            "priority": "P3",
            "root_cause": "Duplicate billing cycle due to order amendment",
            "resolution_notes": "Credited duplicate charge and consolidated billing.",
            "related_log_pattern": "BILLING_DUPLICATE_CHARGE order_id={order_id} amount=",
        },
        {
            "product_type": "Mobile 5G Enterprise",
            "category": "catalog_eligibility",
            "short_description": "Catalog eligibility conflict for 5G add-on",
            "description": "Order rejected by product catalog because the 5G roaming add-on is not eligible for the base plan.",
            "priority": "P3",
            "root_cause": "Product option not eligible for current base product",
            "resolution_notes": "Selected compatible add-on and resubmitted order.",
            "related_log_pattern": "CATALOG_ELIGIBILITY_ERROR product_id=5G_ROAM base_plan=",
        },
    ]

    tickets = []
    for i in range(count):
        template = templates[i % len(templates)]
        idx = i + 1
        order_id = None if random.random() < 0.2 else f"ORD-CCU-{idx:04d}"
        root_cause = template["root_cause"]
        # Forcer exactement 3 tickets 'undetermined' sur les 3 premiers
        if i < 3:
            root_cause = "undetermined"
            template = dict(template)
            template["description"] = "Investigation ongoing; root cause not yet identified."

        ticket = {
            "ticket_id": f"TICK-CCU-{idx:04d}",
            "client_id": f"CLI-{idx:05d}",
            "order_id": order_id,
            "product_type": template["product_type"],
            "short_description": template["short_description"],
            "description": template["description"],
            "priority": template["priority"],
            "category": template["category"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "new" if random.random() < 0.7 else "open",
            "root_cause": root_cause,
            "resolution_notes": template["resolution_notes"] if root_cause != "undetermined" else "",
            "related_log_pattern": template["related_log_pattern"],
        }
        tickets.append(ticket)
    return tickets


def _normalize_ccu_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    """Valide et complète un ticket généré par Anthropic."""
    for field in REQUIRED_FIELDS:
        if field not in ticket or ticket[field] is None:
            if field == "order_id":
                ticket[field] = None
            elif field in ("root_cause", "resolution_notes", "related_log_pattern"):
                ticket[field] = ""
            elif field == "priority":
                ticket[field] = "P3"
            elif field == "category":
                ticket[field] = random.choice(CCU_CATEGORIES)
            elif field == "product_type":
                ticket[field] = random.choice(CCU_PRODUCTS)
            elif field == "created_at":
                ticket[field] = datetime.now(timezone.utc).isoformat()
            elif field == "status":
                ticket[field] = "new"
            elif field == "short_description":
                ticket[field] = ticket.get("description", "No summary")[:80]
            else:
                ticket[field] = "unknown"

    # Nettoyage id
    ticket["ticket_id"] = re.sub(r"[^a-zA-Z0-9_-]+", "_", str(ticket["ticket_id"]))
    ticket["priority"] = str(ticket["priority"]).upper()
    if ticket["priority"] not in {"P1", "P2", "P3", "P4"}:
        ticket["priority"] = "P3"

    return ticket


def generate(
    output_dir: Path,
    count: int = 30,
    push_to_zammad: bool = False,
    max_retries: int = 3,
) -> list[Path]:
    """Génère les tickets CCU via Anthropic et les sauvegarde."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    settings = get_settings()

    if settings.ANTHROPIC_API_KEY:
        logger.info("Génération via Anthropic (%s)...", settings.ANTHROPIC_MODEL)
        for attempt in range(1, max_retries + 1):
            try:
                tickets = _generate_with_anthropic(
                    settings.ANTHROPIC_API_KEY, settings.ANTHROPIC_MODEL, count
                )
                break
            except Exception as exc:
                logger.warning("Échec Anthropic (tentative %s/%s): %s", attempt, max_retries, exc)
                if attempt == max_retries:
                    logger.warning("Fallback sur les tickets déterministes.")
                    tickets = _generate_local_fallback(count)
    else:
        logger.warning("ANTHROPIC_API_KEY non configurée. Utilisation du fallback déterministe.")
        tickets = _generate_local_fallback(count)

    # Garantir au moins 3 tickets 'undetermined'
    undetermined_count = sum(1 for t in tickets if str(t.get("root_cause", "")).strip().lower() == "undetermined")
    if undetermined_count < 3:
        for i in range(3 - undetermined_count):
            if i < len(tickets):
                tickets[i]["root_cause"] = "undetermined"
                tickets[i]["resolution_notes"] = ""

    created: list[Path] = []
    for ticket in tickets:
        ticket = _normalize_ccu_ticket(ticket)
        # Enrichissement du format interne pour graph ingestion + TMF621
        enriched = {
            "ticket_id": ticket["ticket_id"],
            "summary": ticket["short_description"],
            "description": ticket["description"],
            "root_cause": ticket["root_cause"],
            "resolution": ticket["resolution_notes"],
            "tags": [ticket["category"], ticket["product_type"].lower().replace(" ", "_")],
            "priority": ticket["priority"],
            "status": ticket["status"],
            "category": ticket["category"],
            "product_type": ticket["product_type"],
            "client_id": ticket["client_id"],
            "order_id": ticket["order_id"],
            "created_at": ticket["created_at"],
            "related_log_pattern": ticket["related_log_pattern"],
            "tmf621": {
                "id": ticket["ticket_id"],
                "href": f"/tmf621/troubleTicket/{ticket['ticket_id']}",
                "creationDate": ticket["created_at"],
                "description": ticket["short_description"],
                "severity": ticket["priority"],
                "priority": ticket["priority"],
                "status": ticket["status"],
                "type": ticket["category"],
                "relatedParty": [{"id": ticket["client_id"], "role": "customer"}],
                "relatedObject": [
                    {"id": ticket["order_id"], "role": "order"}
                ] if ticket["order_id"] else [],
            },
        }
        path = output_dir / f"{ticket['ticket_id']}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(enriched, f, indent=2, ensure_ascii=False)
        created.append(path)

        if push_to_zammad:
            zammad_ticket = {
                "ticket_id": ticket["ticket_id"],
                "short_description": ticket["short_description"],
                "description": ticket["description"],
                "priority": ticket["priority"],
                "category": ticket["category"],
                "status": ticket["status"],
                "root_cause": ticket["root_cause"],
                "resolution_notes": ticket["resolution_notes"],
                "client_id": ticket["client_id"],
                "product_type": ticket["product_type"],
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

    logger.info("%s tickets CCU générés dans %s", len(created), output_dir)
    return created


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Génère des tickets CCU synthétiques")
    parser.add_argument("--output", default=str(get_settings().MOCK_TICKETS_DIR), help="Dossier de sortie")
    parser.add_argument("--count", type=int, default=30, help="Nombre de tickets à générer")
    parser.add_argument("--push-to-zammad", action="store_true", help="Pousser les tickets dans Zammad")
    parser.add_argument("--seed", type=int, default=42, help="Seed aléatoire")
    args = parser.parse_args()

    random.seed(args.seed)
    generate(
        output_dir=Path(args.output),
        count=args.count,
        push_to_zammad=args.push_to_zammad,
    )
