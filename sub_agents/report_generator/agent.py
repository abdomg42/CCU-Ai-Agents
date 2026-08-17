"""Générateur de rapport PDF à partir de l'état LangGraph.

Le PDF est généré directement en Python sans template HTML ni WeasyPrint.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import get_settings
from shared.audit_logger import audit_logger
from shared.state import GraphState
from sub_agents.intake_parser.schemas import IncidentSchema

from .pdf_renderer import generate_diagnostic_report

logger = logging.getLogger(__name__)


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


def _generate_incident_id(state: GraphState) -> str:
    incident = state.incident or {}
    parsed = _as_parsed(state.parsed_incident)
    seed = (
        f"{incident.get('title', '')}-{incident.get('description', '')}-"
        f"{parsed.customer_id or ''}-{parsed.service_id or ''}"
    )
    return f"INC-CCU-{hashlib.sha256(seed.encode()).hexdigest()[:8].upper()}"


def _confidence_label(confidence: str | None) -> str:
    key = (confidence or "").lower()
    if key in {"forte", "high"}:
        return "high"
    if key == "moyenne":
        return "medium"
    return "low"


def _build_sources(state: GraphState) -> list[str]:
    sources: list[str] = []
    if state.logs:
        sources.extend(state.logs.get("source_ids", []))
    if state.customer_context:
        sources.extend(state.customer_context.get("source_ids", []))
    if state.similar_tickets:
        sources.extend(state.similar_tickets.get("source_ids", []))
    return sources


def _build_report_data(state: GraphState) -> dict[str, Any]:
    """Construit le dictionnaire de données attendu par le renderer PDF."""
    incident = state.incident or {}
    parsed = _as_parsed(state.parsed_incident)
    root_cause = state.root_cause or {}
    mapping = state.ticket_mapping or {}

    report_id = f"REP-{uuid.uuid4().hex[:12].upper()}"
    generated_at = datetime.now(timezone.utc).isoformat()
    incident_id = _generate_incident_id(state)
    detected_at = incident.get("detected_at") or generated_at

    return {
        "title": incident.get("title", "AI Diagnostic Report"),
        "report_id": report_id,
        "generated_at": generated_at,
        "incident_id": incident_id,
        "client_id": parsed.customer_id or incident.get("customer_id") or "N/A",
        "order_id": parsed.order_id or incident.get("order_id"),
        "product_type": parsed.incident_type or incident.get("incident_type") or "N/A",
        "category": parsed.incident_type or incident.get("incident_type") or "N/A",
        "priority": parsed.priority or incident.get("priority") or "P3",
        "detected_at": detected_at,
        "what_happened": state.sanitized_what_happened or incident.get("description", ""),
        "confidence_level": root_cause.get("confidence", "low"),
        "confidence_label": _confidence_label(root_cause.get("confidence")),
        "root_cause": state.sanitized_root_cause or root_cause.get("cause", "undetermined"),
        "sources": _build_sources(state),
        "mapping_status": mapping.get("status", "created_new"),
        "mapping_ticket_id": mapping.get("ticket_id"),
        "mapping_score": str(mapping.get("similarity_score", 0.0)),
        "recommendation": state.sanitized_recommendation or "",
    }


class ReportGeneratorAgent:
    def __init__(self) -> None:
        self.settings = get_settings()

    def run(self, state: GraphState) -> dict[str, Any]:
        incident_id = _generate_incident_id(state)
        audit_logger.log("report_generator_start", {"incident_id": incident_id})

        data = _build_report_data(state)
        output_path = self.settings.REPORTS_DIR / f"{incident_id}.pdf"

        try:
            final_path = generate_diagnostic_report(data, output_path)
            audit_logger.log("report_generator_pdf", {"path": str(final_path)})
        except Exception as exc:
            audit_logger.log("report_generator_error", {"error": str(exc)})
            logger.warning("Échec génération PDF : %s", exc)
            raise

        return {"report_path": str(final_path)}


def run_report_generator(state: GraphState) -> dict[str, Any]:
    return ReportGeneratorAgent().run(state)
