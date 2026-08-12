"""Agent d'explication de remédiation.

Produit uniquement un texte informatif structuré (What happened / Why /
Recommendation). Aucune action technique n'est générée ni exécutée.
"""
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from sub_agents.intake_parser.schemas import IncidentSchema
from .prompt import REMEDIATION_EXPLAINER_SYSTEM_PROMPT
from .schemas import RemediationExplanationSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class RemediationExplainerAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _explain(self, state: GraphState) -> RemediationExplanationSchema:
        root = state.root_cause or {}
        cause = root.get("cause", "indéterminée")
        explanation = root.get("explanation", "")
        source_ids = root.get("source_ids", [])
        parsed = _as_parsed(state.parsed_incident)

        if cause.lower() == "indéterminée":
            text = (
                "What happened: The reported incident could not be correlated with a known root cause. "
                f"Customer / service: {parsed.customer_id or 'unknown'} / {parsed.service_id or 'unknown'}.\n\n"
                "Why: No sufficient source (logs, customer context or similar ticket) could ground a precise diagnosis.\n\n"
                "Recommendation: Escalate to the support team for manual investigation. "
                "Collect additional logs and verify the service configuration before any action."
            )
            return RemediationExplanationSchema(explanation=text)

        text = (
            f"What happened: Incident on {parsed.incident_type or 'service'} "
            f"for customer {parsed.customer_id or 'unknown'}. "
            f"Sources consulted: {', '.join(source_ids) or 'none'}.\n\n"
            f"Why: {explanation or 'Root cause identified: ' + cause}\n\n"
            "Recommendation: Review the identified cause with the relevant operations team. "
            "No automatic action is performed by this agent; human validation is required."
        )
        return RemediationExplanationSchema(explanation=text)

    def run(self, state: GraphState) -> dict[str, Any]:
        audit_logger.log("remediation_explain_start", {"root_cause": state.root_cause})
        result = self._explain(state)

        if not self.llm.settings.MOCK_LLM:
            try:
                user_msg = (
                    f"Incident: {state.parsed_incident}\n"
                    f"Root cause: {state.root_cause}\n"
                    f"Similar tickets: {state.similar_tickets}\n"
                    f"Logs summary: {state.logs}\n"
                    f"Customer context: {state.customer_context}"
                )
                result = self.llm.invoke_structured(
                    REMEDIATION_EXPLAINER_SYSTEM_PROMPT, user_msg, RemediationExplanationSchema
                )
            except Exception as exc:
                audit_logger.log("remediation_explain_llm_fallback", {"error": str(exc)})

        audit_logger.log("remediation_explain_end", {"result": result.model_dump()})
        return {"remediation_explanation": result.explanation}


def run_remediation_explanation(state: GraphState) -> dict[str, Any]:
    return RemediationExplainerAgent().run(state)
