"""Agent de conversation générale avec récupération de contexte.

Répond aux questions libres de l'utilisateur. Si le message contient des
identifiants CCU (service, commande, client), l'agent consulte les logs,
le contexte client et les tickets historiques pour enrichir sa réponse.
"""
from typing import Any

from shared.llm_client import LLMClient
from shared.audit_logger import audit_logger
from shared.state import GraphState
from sub_agents.intake_parser.agent import IntakeParserAgent
from sub_agents.logs_investigator.agent import run_logs
from sub_agents.context_agent.agent import run_context
from sub_agents.rag_ticket_search.agent import run_rag
from .prompt import CHAT_SYSTEM_PROMPT


class ChatAgent:
    def __init__(self) -> None:
        self.llm = LLMClient()

    def _extract_context(self, user_message: str) -> dict[str, Any]:
        """Extrait les identifiants CCU et récupère logs/contexte/tickets.

        Returns:
            Dictionnaire avec les résultats des agents collecteurs, ou des
            champs vides si aucun identifiant n'est trouvé.
        """
        parser = IntakeParserAgent()
        parse_result = parser.run(GraphState(incident={
            "title": user_message,
            "description": user_message,
        }))
        parsed = parse_result.get("parsed_incident") or {}

        has_id = any(
            parsed.get(k)
            for k in ("service_id", "order_id", "customer_id", "incident_type")
        )
        if not has_id:
            return {}

        state = GraphState(parsed_incident=parsed)
        try:
            logs = run_logs(state)
        except Exception as exc:
            audit_logger.log("chat_logs_error", {"error": str(exc)})
            logs = {}
        try:
            context = run_context(state)
        except Exception as exc:
            audit_logger.log("chat_context_error", {"error": str(exc)})
            context = {}
        try:
            rag = run_rag(state)
        except Exception as exc:
            audit_logger.log("chat_rag_error", {"error": str(exc)})
            rag = {}

        return {
            "parsed": parsed,
            "logs": logs.get("logs"),
            "customer_context": context.get("customer_context"),
            "similar_tickets": rag.get("similar_tickets"),
        }

    def _build_retrieval_prompt(
        self,
        user_message: str,
        history: list[dict[str, str]] | None,
        retrieval: dict[str, Any],
    ) -> str:
        """Construit le prompt utilisateur avec historique et contexte récupéré."""
        parts: list[str] = []

        if history:
            for turn in history:
                role = turn.get("role", "user")
                content = turn.get("content", "")
                parts.append(f"{role}: {content}")

        if retrieval:
            parts.append("--- Contexte CCU récupéré ---")
            parsed = retrieval.get("parsed") or {}
            if parsed:
                parts.append(
                    f"Identifiants extraits: service={parsed.get('service_id')}, "
                    f"order={parsed.get('order_id')}, customer={parsed.get('customer_id')}, "
                    f"type={parsed.get('incident_type')}"
                )
            logs = retrieval.get("logs") or {}
            if logs:
                parts.append(f"Logs: {logs.get('summary', 'N/A')}")
                for log in logs.get("relevant_logs", [])[:3]:
                    parts.append(
                        f"  - [{log.get('severity')}] {log.get('source')}: {log.get('message')}"
                    )
            ctx = retrieval.get("customer_context") or {}
            if ctx:
                parts.append(
                    f"Client: {ctx.get('customer_name')} ({ctx.get('customer_id')}), "
                    f"segment={ctx.get('segment')}, risques={ctx.get('risk_factors', [])}"
                )
                subscription = ctx.get("subscription") or {}
                if subscription:
                    parts.append(
                        f"Abonnement: {subscription.get('service_id')} "
                        f"({subscription.get('offer')}) - statut {subscription.get('status')}"
                    )
            rag = retrieval.get("similar_tickets") or {}
            if rag and rag.get("similar_tickets"):
                parts.append("Tickets historiques similaires:")
                for t in rag["similar_tickets"][:3]:
                    parts.append(
                        f"  - {t.get('ticket_id')}: {t.get('summary')} "
                        f"(cause={t.get('root_cause')}, score={t.get('score', 0):.2f})"
                    )
            parts.append("--- Fin du contexte ---")

        parts.append(f"user: {user_message}")
        return "\n".join(parts)

    def run(
        self,
        user_message: str,
        history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """Génère une réponse conversationnelle, éventuellement enrichie par RAG."""
        audit_logger.log("chat_start", {"message": user_message})

        retrieval = self._extract_context(user_message)
        user_prompt = self._build_retrieval_prompt(user_message, history, retrieval)

        if self.llm.settings.MOCK_LLM:
            if retrieval:
                parsed = retrieval.get("parsed") or {}
                response = (
                    f"D'après les données CCU récupérées pour "
                    f"{parsed.get('service_id') or parsed.get('customer_id') or 'cet identifiant'}, "
                    "je peux vous dire que des informations sont disponibles. "
                    "Passez en mode Diagnostic pour une analyse complète."
                )
            else:
                response = (
                    f"Vous avez demandé : '{user_message}'. "
                    "Je suis en mode conversation. Passez en mode Diagnostic pour analyser un incident."
                )
        else:
            try:
                response = self.llm.invoke_text(CHAT_SYSTEM_PROMPT, user_prompt)
            except Exception as exc:
                audit_logger.log("chat_error", {"error": str(exc)})
                response = (
                    "Désolé, je n'ai pas pu générer de réponse pour le moment. "
                    "Vérifiez que le service LLM est disponible."
                )

        audit_logger.log("chat_end", {"response": response, "retrieval": bool(retrieval)})
        return {
            "chat_response": response,
            "retrieval_used": bool(retrieval),
            "retrieved_context": retrieval,
        }


def run_chat(
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Point d'entrée simple pour l'agent de conversation."""
    return ChatAgent().run(user_message, history)
