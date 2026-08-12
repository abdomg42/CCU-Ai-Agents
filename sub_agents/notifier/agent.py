"""Agent notifier : envoi email + note interne Zammad.

Aucune action technique n'est exécutée. Le notifier informe simplement les
destinataires configurés et ajoute une trace dans le ticket.
"""
from __future__ import annotations

import logging
from typing import Any

from shared.audit_logger import audit_logger
from shared.state import GraphState
from sub_agents.intake_parser.schemas import IncidentSchema
from .email_client import EmailClient
from .ticket_note import add_diagnostic_note

logger = logging.getLogger(__name__)


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


def _confidence_label(state: GraphState) -> str:
    root = state.root_cause or {}
    confidence = str(root.get("confidence", "")).lower()
    if confidence == "forte":
        return "high"
    if confidence == "moyenne":
        return "medium"
    return "low"


def _incident_id(state: GraphState) -> str:
    if state.report_path:
        path = state.report_path
        # Le nom de fichier est reports/{incident_id}.pdf ou .html
        return path.split("/")[-1].split(".")[0]
    parsed = _as_parsed(state.parsed_incident)
    return f"INC-{parsed.customer_id or 'UNKNOWN'}"


class NotifierAgent:
    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("notifier_start", {"report_path": state.report_path})

        incident_id = _incident_id(state)
        confidence_label = _confidence_label(state)
        report_path = state.report_path or ""
        mapping = state.ticket_mapping or {}

        email_result = EmailClient().send_report(
            incident_id=incident_id,
            confidence_label=confidence_label,
            report_path=report_path,
        )

        zammad_result = {"added": False}
        if mapping.get("ticket_id"):
            zammad_result = add_diagnostic_note(
                ticket_id=mapping["ticket_id"],
                incident_id=incident_id,
                report_path=report_path,
            )

        audit_logger.log(
            "notifier_end",
            {
                "email_sent": email_result.get("sent"),
                "recipients": email_result.get("recipients"),
                "zammad_note_added": zammad_result.get("added"),
            },
        )

        return {
            "email_sent": email_result.get("sent", False),
            "email_recipients": email_result.get("recipients", []),
            "zammad_note_added": zammad_result.get("added", False),
        }


def run_notifier(state: GraphState) -> dict[str, Any]:
    return NotifierAgent().run(state)
