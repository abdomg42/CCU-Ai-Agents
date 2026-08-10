"""Agent d'intake : normalise l'incident brut."""
import re
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from .prompt import INTAKE_SYSTEM_PROMPT
from .schemas import IncidentSchema


class IntakeParserAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _extract_field(self, text: str, patterns: list[str]) -> str | None:
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _heuristic_parse(self, incident: dict[str, Any]) -> IncidentSchema:
        text = incident.get("description", "") + " " + incident.get("title", "")
        service_id = self._extract_field(text, [
            r"service[_\-]?id\s*[:=]\s*([a-z0-9\-]+)",
            r"service\s+([a-z0-9\-]+)",
            r"\b(svc-[a-z0-9\-]+)\b",
        ])
        order_id = self._extract_field(text, [
            r"order[_\-]?id\s*[:=]\s*([a-z0-9\-]+)",
            r"commande\s+([a-z0-9\-]+)",
            r"\b(ord-[0-9\-]+)\b",
        ])
        customer_id = self._extract_field(text, [
            r"customer[_\-]?id\s*[:=]\s*([a-z0-9\-]+)",
            r"client\s+([a-z0-9\-]+)",
            r"\b(acc-[0-9]+)\b",
        ])
        incident_type = None
        lowered = text.lower()
        if "fibre" in lowered or "fiber" in lowered or "olt" in lowered:
            incident_type = "fibre"
        elif "sim" in lowered or "hss" in lowered or "hlr" in lowered or "iccid" in lowered or "imsi" in lowered:
            incident_type = "sim"
        elif "mobile" in lowered or "crm" in lowered or "acknowledged" in lowered or "cellulaire" in lowered or "5g" in lowered:
            incident_type = "mobile"
        elif "vlan" in lowered or "switch" in lowered or "lan" in lowered:
            incident_type = "lan"
        elif "facture" in lowered or "billing" in lowered or "facturation" in lowered:
            incident_type = "billing"
        else:
            incident_type = "autre"

        priority = "P3"
        if any(k in lowered for k in ("coupure", "down", "outage", "perte", "bloquée")):
            priority = "P2"
        if any(k in lowered for k in ("critique", "p1", "indisponibilité totale")):
            priority = "P1"

        return IncidentSchema(
            service_id=service_id,
            order_id=order_id,
            customer_id=customer_id,
            incident_type=incident_type,
            description=incident.get("description") or incident.get("title", ""),
            priority=priority,
        )

    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("intake_start", {"incident": state.incident})
        parsed = self._heuristic_parse(state.incident)

        # Si le LLM est disponible, on lui demande de valider/ajuster la structure.
        if not self.llm.settings.MOCK_LLM:
            try:
                user_msg = f"Incident brut : {state.incident}\nParsing heuristique proposé : {parsed.model_dump()}"
                parsed = self.llm.invoke_structured(
                    INTAKE_SYSTEM_PROMPT, user_msg, IncidentSchema
                )
            except Exception as exc:
                audit_logger.log("intake_llm_fallback", {"error": str(exc)})

        audit_logger.log("intake_end", {"parsed_incident": parsed.model_dump()})
        return {"parsed_incident": parsed.model_dump()}


def run_intake(state: GraphState) -> dict[str, Any]:
    return IntakeParserAgent().run(state)
