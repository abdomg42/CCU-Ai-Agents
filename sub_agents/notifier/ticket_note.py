"""Ajout d'une note interne Zammad sur le ticket concerné.

Cette opération est purement informative (type 'note', internal=True). Aucune
action technique n'est exécutée.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from tools.ticketing_client import ZammadClient

logger = logging.getLogger(__name__)


def _extract_zammad_id(ticket_id: str) -> str | None:
    """Extrait l'ID Zammad d'une chaîne du type 'TICK-CCU-XXXX (Zammad #12345)'."""
    match = re.search(r"Zammad\s+#(\d+)", ticket_id)
    if match:
        return match.group(1)
    return None


def add_diagnostic_note(ticket_id: str, incident_id: str, report_path: str) -> dict[str, Any]:
    """Ajoute une note interne sur le ticket Zammad."""
    zammad_id = _extract_zammad_id(ticket_id)
    if not zammad_id:
        # Si l'ID ne contient pas d'ID Zammad, on ne peut pas poster de note.
        logger.warning("Impossible d'ajouter une note Zammad : ID Zammad introuvable dans %s", ticket_id)
        return {"added": False, "reason": "no_zammad_id", "ticket_id": ticket_id}

    body = (
        f"Diagnostic agent report generated for incident {incident_id}.\n"
        f"Report path: {report_path}\n\n"
        "Full report sent by email."
    )

    try:
        client = ZammadClient()
        result = client.add_note(zammad_id, body, internal=True)
        logger.info("Note Zammad ajoutée sur le ticket %s", zammad_id)
        return {"added": True, "zammad_id": zammad_id, "note_id": result.get("id")}
    except Exception as exc:
        logger.warning("Échec ajout note Zammad : %s", exc)
        return {"added": False, "reason": str(exc), "ticket_id": ticket_id}
