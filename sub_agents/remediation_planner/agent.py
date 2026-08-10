"""Agent de planification de remédiation."""
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from .prompt import REMEDIATION_SYSTEM_PROMPT
from .schemas import RemediationSchema, ProposedAction
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class RemediationPlannerAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _plan(self, state: GraphState) -> RemediationSchema:
        root = state.root_cause or {}
        cause = root.get("cause", "indéterminée")
        source_ids = root.get("source_ids", [])
        parsed = _as_parsed(state.parsed_incident)

        if cause.lower() == "indéterminée":
            return RemediationSchema(actions=[
                ProposedAction(
                    action="Escalade vers l'équipe support pour investigation manuelle",
                    justification="Cause racine indéterminée : investigation supplémentaire nécessaire.",
                    source_ids=[],
                )
            ])

        actions = []
        if "fibre" in parsed.incident_type or "signal" in cause.lower():
            actions.append(ProposedAction(
                action="Envoyer un technicien sur site pour contrôle du point de terminaison optique (PTO)",
                justification="Perte de signal fibre optique détectée.",
                source_ids=source_ids,
            ))
        if "crm" in cause.lower() or "acknowledged" in cause.lower():
            actions.append(ProposedAction(
                action="Relancer l'appel CRM et forcer le passage de la commande en 'inProgress' si le retry réussit",
                justification="Commande bloquée par un timeout CRM.",
                source_ids=source_ids,
            ))
        if "hlr" in cause.lower() or "hss" in cause.lower() or "iccid" in cause.lower():
            actions.append(ProposedAction(
                action="Reprovisionner l'ICCID dans le HLR/HSS puis relancer l'activation SIM",
                justification="SIM non reconnue par le HSS.",
                source_ids=source_ids,
            ))
        if "vlan" in cause.lower():
            actions.append(ProposedAction(
                action="Corriger le VLAN sur le port switch concerné",
                justification="VLAN mismatch entre service et port switch.",
                source_ids=source_ids,
            ))
        if not actions:
            actions.append(ProposedAction(
                action="Investigation complémentaire sur la cause identifiée",
                justification=f"Cause identifiée : {cause}.",
                source_ids=source_ids,
            ))

        return RemediationSchema(actions=actions)

    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("remediation_start", {"root_cause": state.root_cause})
        result = self._plan(state)

        if not self.llm.settings.MOCK_LLM:
            try:
                user_msg = f"Cause racine : {state.root_cause}\nPlan proposé : {result.model_dump()}"
                result = self.llm.invoke_structured(REMEDIATION_SYSTEM_PROMPT, user_msg, RemediationSchema)
            except Exception as exc:
                audit_logger.log("remediation_llm_fallback", {"error": str(exc)})

        audit_logger.log("remediation_end", {"result": result.model_dump()})
        return {"remediation": result.model_dump()}


def run_remediation(state: GraphState) -> dict[str, Any]:
    return RemediationPlannerAgent().run(state)
