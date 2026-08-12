"""Agent de mapping et création de tickets.

1. Recherche un ticket similaire via Neo4j GraphRAG.
2. Si score >= seuil configuré -> linked_to_existing.
3. Sinon -> crée un nouveau ticket dans Zammad et retourne created_new.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from shared.audit_logger import audit_logger
from shared.state import GraphState
from config.settings import get_settings
from graph.queries import search_similar_incidents
from tools.ticketing_client import push_ticket_to_zammad
from sub_agents.intake_parser.schemas import IncidentSchema
from .schemas import TicketMappingResult

logger = logging.getLogger(__name__)


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


def _pick_anchor_id(parsed: IncidentSchema) -> str:
    return (
        parsed.service_id
        or parsed.order_id
        or parsed.customer_id
        or parsed.incident_type
        or ""
    )


def _build_query(parsed: IncidentSchema) -> str:
    parts = [parsed.incident_type or "", parsed.description or ""]
    return " ".join(p for p in parts if p).strip()


def _generate_ticket_id(state: GraphState) -> str:
    incident = state.incident or {}
    parsed = _as_parsed(state.parsed_incident)
    seed = f"{parsed.customer_id or ''}-{parsed.service_id or ''}-{incident.get('title', '')}"
    h = hashlib.sha256(seed.encode()).hexdigest()[:8].upper()
    return f"TICK-CCU-{h}"


class TicketManagerAgent:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _search_similar(self, state: GraphState) -> tuple[str | None, float]:
        parsed = _as_parsed(state.parsed_incident)
        anchor_id = _pick_anchor_id(parsed)
        query = _build_query(parsed)

        if not anchor_id or not query:
            audit_logger.log("ticket_mapping_skip", {"reason": "missing anchor_id or query"})
            return None, 0.0

        try:
            results = search_similar_incidents(
                incident_id=anchor_id,
                query_text=query,
                top_k=1,
            )
        except Exception as exc:
            audit_logger.log("ticket_mapping_search_error", {"error": str(exc)})
            return None, 0.0

        if not results:
            return None, 0.0

        best = results[0]
        audit_logger.log(
            "ticket_mapping_candidate",
            {"ticket_id": best.ticket_id, "score": best.score},
        )
        return best.ticket_id, best.score

    def _create_new_ticket(self, state: GraphState) -> str:
        incident = state.incident or {}
        parsed = _as_parsed(state.parsed_incident)
        root_cause = state.root_cause or {}

        ticket_id = _generate_ticket_id(state)
        title = incident.get("title", "CCU incident")
        description = incident.get("description", title)
        priority = parsed.priority or incident.get("priority", "P3")

        payload = {
            "ticket_id": ticket_id,
            "short_description": title,
            "description": description,
            "priority": priority,
            "category": parsed.incident_type or "ccu",
            "status": "new",
            "root_cause": root_cause.get("cause", "undetermined"),
            "resolution_notes": "",
            "client_id": parsed.customer_id or "nicole.braun@zammad.org",
            "product_type": parsed.incident_type or "ccu",
        }

        try:
            result = push_ticket_to_zammad(payload)
            zammad_id = result.get("id")
            if zammad_id:
                audit_logger.log(
                    "ticket_mapping_created_zammad",
                    {"local_id": ticket_id, "zammad_id": zammad_id},
                )
                return f"{ticket_id} (Zammad #{zammad_id})"
        except Exception as exc:
            audit_logger.log("ticket_mapping_zammad_fallback", {"error": str(exc)})

        return ticket_id

    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("ticket_mapping_start", {"parsed": state.parsed_incident})

        ticket_id, score = self._search_similar(state)
        threshold = self.settings.TICKET_MAPPING_SIMILARITY_THRESHOLD

        if ticket_id and score >= threshold:
            result = TicketMappingResult(
                status="linked_to_existing",
                ticket_id=ticket_id,
                similarity_score=round(score, 4),
            )
        else:
            new_ticket_id = self._create_new_ticket(state)
            result = TicketMappingResult(
                status="created_new",
                ticket_id=new_ticket_id,
                similarity_score=0.0,
            )

        audit_logger.log("ticket_mapping_end", {"result": result.model_dump()})
        return {"ticket_mapping": result.model_dump()}


def run_ticket_manager(state: GraphState) -> dict[str, Any]:
    return TicketManagerAgent().run(state)
