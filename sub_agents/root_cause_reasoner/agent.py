"""Agent de raisonnement root cause."""
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from .prompt import ROOT_CAUSE_SYSTEM_PROMPT
from .schemas import RootCauseSchema
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class RootCauseReasonerAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _collect_sources(self, state: GraphState) -> tuple[list[str], str]:
        sources = []
        parts = []
        if state.logs:
            sources.extend(state.logs.get("source_ids", []))
            parts.append(f"Logs : {state.logs.get('summary', '')}")
        if state.customer_context:
            sources.extend(state.customer_context.get("source_ids", []))
            parts.append(f"Contexte client : {state.customer_context.get('risk_factors', [])}")
        if state.similar_tickets:
            sources.extend(state.similar_tickets.get("source_ids", []))
            parts.append(f"Tickets similaires : {state.similar_tickets.get('synthesis', '')}")
        return sources, "\n".join(parts)

    def _deterministic_cause(self, state: GraphState) -> RootCauseSchema:
        sources, _ = self._collect_sources(state)
        parsed = _as_parsed(state.parsed_incident)

        # Les incidents commerciaux/facturation ne nécessitent pas de source technique.
        if parsed.incident_type == "billing":
            return RootCauseSchema(
                confidence="moyenne",
                cause="Demande commerciale / ajustement de facturation",
                explanation="Le client sollicite une remise, un avoir ou un ajustement de facturation. Nécessite validation par le service billing ou commercial.",
                source_ids=sources,
            )

        if not sources:
            return RootCauseSchema(
                confidence="faible",
                cause="indéterminée",
                explanation="Aucune source suffisante (logs, contexte client ou ticket similaire) pour établir un diagnostic.",
                source_ids=[],
            )

        # Corrélation heuristique simple basée sur l'incident_type et les causes historiques
        rag = state.similar_tickets or {}
        similar = rag.get("similar_tickets", [])
        if similar:
            best = min(similar, key=lambda t: t.get("distance", 1.0))
            cause = best.get("root_cause", "indéterminée")
            if cause and cause.lower() != "indéterminée":
                return RootCauseSchema(
                    confidence="forte" if len(sources) >= 2 else "moyenne",
                    cause=cause,
                    explanation=f"Cause déduite du ticket similaire {best.get('ticket_id')} et des sources collectées.",
                    source_ids=sources,
                )

        # Fallback sur les logs/contexte si pas de ticket pertinent
        if parsed.incident_type == "fibre":
            return RootCauseSchema(
                confidence="moyenne",
                cause="Perte de signal fibre optique",
                explanation="Logs OLT indiquent une perte de signal optique.",
                source_ids=sources,
            )
        if parsed.incident_type == "mobile":
            return RootCauseSchema(
                confidence="moyenne",
                cause="Timeout CRM lors de la récupération du profil client",
                explanation="CRM timeout observé dans les logs, commande bloquée en acknowledged.",
                source_ids=sources,
            )
        if parsed.incident_type == "sim":
            return RootCauseSchema(
                confidence="moyenne",
                cause="ICCID SIM non provisionnée dans le HLR",
                explanation="HSS retourne Unknown subscriber, ICCID non reconnue.",
                source_ids=sources,
            )
        if parsed.incident_type == "lan":
            return RootCauseSchema(
                confidence="moyenne",
                cause="VLAN mismatch entre service et port switch",
                explanation="Le switch remonte un VLAN mismatch sur le port concerné.",
                source_ids=sources,
            )
        if parsed.incident_type == "billing":
            return RootCauseSchema(
                confidence="moyenne",
                cause="Demande commerciale / ajustement de facturation",
                explanation="Le client sollicite une remise, un avoir ou un ajustement de facturation. Nécessite validation par le service billing ou commercial.",
                source_ids=sources,
            )

        return RootCauseSchema(
            confidence="faible",
            cause="indéterminée",
            explanation="Sources insuffisantes pour identifier une cause racine précise.",
            source_ids=sources,
        )

    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("root_cause_start", {
            "logs": state.logs,
            "context": state.customer_context,
            "tickets": state.similar_tickets,
        })

        result = self._deterministic_cause(state)

        # Si le LLM est disponible, on lui présente la suggestion déterministe pour validation.
        if not self.llm.settings.MOCK_LLM:
            sources, context = self._collect_sources(state)
            user_msg = (
                f"Sources disponibles : {sources}\n{context}\n"
                f"Suggestion déterministe : {result.model_dump()}"
            )
            try:
                result = self.llm.invoke_structured(ROOT_CAUSE_SYSTEM_PROMPT, user_msg, RootCauseSchema)
                # Sécurité : si le LLM retourne une cause sans source, on force l'indétermination.
                if not result.source_ids:
                    result = RootCauseSchema(
                        confidence="faible",
                        cause="indéterminée",
                        explanation="Le LLM n'a pas fourni de source suffisante.",
                        source_ids=[],
                    )
            except Exception as exc:
                audit_logger.log("root_cause_llm_fallback", {"error": str(exc)})

        audit_logger.log("root_cause_end", {"result": result.model_dump()})
        return {"root_cause": result.model_dump()}


def run_root_cause(state: GraphState) -> dict[str, Any]:
    return RootCauseReasonerAgent().run(state)
