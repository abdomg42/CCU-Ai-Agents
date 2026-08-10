"""Agent RAG de recherche de tickets similaires via Neo4j GraphRAG."""
from typing import Any

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from config.settings import get_settings
from graph.queries import search_similar_incidents
from .prompt import RAG_SYSTEM_PROMPT
from .schemas import RAGSchema
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class RAGTicketSearchAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()

    @staticmethod
    def _pick_anchor_id(parsed: IncidentSchema) -> str:
        """Choisit le meilleur identifiant d'ancrage dans le graphe."""
        return (
            parsed.service_id
            or parsed.order_id
            or parsed.customer_id
            or parsed.incident_type
            or ""
        )

    def run(self, state: GraphState) -> dict[str, Any]:
        parsed = _as_parsed(state.parsed_incident)
        audit_logger.log("rag_start", {"parsed": parsed.model_dump()})

        query = f"{parsed.incident_type or ''} {parsed.description or ''}".strip()
        anchor_id = self._pick_anchor_id(parsed)

        similar: list[dict[str, Any]] = []
        source_ids: list[str] = []

        if anchor_id and query:
            try:
                results = search_similar_incidents(
                    incident_id=anchor_id,
                    query_text=query,
                    top_k=3,
                )
                for r in results:
                    similar.append(
                        {
                            "ticket_id": r.ticket_id,
                            "summary": r.summary,
                            "description": r.description,
                            "root_cause": r.root_cause,
                            "resolution": r.resolution,
                            "score": r.score,
                            "distance": 1.0 - r.score,
                        }
                    )
                    source_ids.append(r.ticket_id)
            except Exception as exc:
                audit_logger.log("rag_graph_error", {"error": str(exc)})
        else:
            audit_logger.log("rag_skip", {"reason": "missing anchor_id or query"})

        result = RAGSchema(
            similar_tickets=similar,
            synthesis=self._build_synthesis(similar),
            source_ids=source_ids,
        )

        if not self.llm.settings.MOCK_LLM and similar:
            try:
                user_msg = f"Tickets similaires : {similar}"
                result = self.llm.invoke_structured(RAG_SYSTEM_PROMPT, user_msg, RAGSchema)
            except Exception as exc:
                audit_logger.log("rag_llm_fallback", {"error": str(exc)})

        audit_logger.log("rag_end", {"result": result.model_dump()})
        return {"similar_tickets": result.model_dump()}

    def _build_synthesis(self, similar: list[dict]) -> str:
        if not similar:
            return "Aucun ticket historique similaire trouvé."
        causes = {t["root_cause"] for t in similar if t.get("root_cause")}
        return f"Causes historiques possibles : {', '.join(causes)}."


def run_rag(state: GraphState) -> dict[str, Any]:
    return RAGTicketSearchAgent().run(state)
