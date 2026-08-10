"""Agent RAG de recherche de tickets similaires via ChromaDB."""
import glob
import json
from typing import Any

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from shared.llm_client import LLMClient
from shared.state import GraphState
from shared.audit_logger import audit_logger
from config.settings import get_settings
from .prompt import RAG_SYSTEM_PROMPT
from .schemas import RAGSchema
from sub_agents.intake_parser.schemas import IncidentSchema


def _as_parsed(incident: dict[str, Any]) -> IncidentSchema:
    return IncidentSchema(**incident) if incident else IncidentSchema()


class RAGTicketSearchAgent:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm = LLMClient()
        self.client = chromadb.PersistentClient(path=str(self.settings.CHROMA_PERSIST_DIR))
        self.embedding_fn = SentenceTransformerEmbeddingFunction(model_name=self.settings.EMBEDDING_MODEL)
        self.collection = self.client.get_or_create_collection(
            name=self.settings.TICKETS_COLLECTION,
            embedding_function=self.embedding_fn,
        )
        self._index_tickets_if_empty()

    def _index_tickets_if_empty(self) -> None:
        if self.collection.count() > 0:
            return
        tickets = []
        for path in glob.glob(str(self.settings.MOCK_TICKETS_DIR / "*.json")):
            with open(path, encoding="utf-8") as f:
                tickets.append(json.load(f))
        documents = [t["description"] for t in tickets]
        metadatas = [{"ticket_id": t["ticket_id"], "root_cause": t["root_cause"], "resolution": t["resolution"]} for t in tickets]
        ids = [t["ticket_id"] for t in tickets]
        if documents:
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

    def run(self, state: GraphState) -> dict[str, Any]:
        parsed = _as_parsed(state.parsed_incident)
        audit_logger.log("rag_start", {"parsed": parsed.model_dump()})
        query = f"{parsed.incident_type or ''} {parsed.description or ''}"
        results = self.collection.query(query_texts=[query], n_results=3)

        similar = []
        source_ids = []
        for meta, distance in zip(results.get("metadatas", [[]])[0], results.get("distances", [[]])[0]):
            if meta:
                similar.append({
                    "ticket_id": meta.get("ticket_id"),
                    "root_cause": meta.get("root_cause"),
                    "resolution": meta.get("resolution"),
                    "distance": distance,
                })
                source_ids.append(meta.get("ticket_id"))

        result = RAGSchema(
            similar_tickets=similar,
            synthesis=self._build_synthesis(similar),
            source_ids=source_ids,
        )

        if not self.llm.settings.MOCK_LLM:
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
