from pydantic import BaseModel, Field


class RAGSchema(BaseModel):
    """Résultat de la recherche RAG de tickets."""

    similar_tickets: list[dict] = Field(default_factory=list, description="Tickets similaires avec métadonnées")
    synthesis: str = Field(..., description="Synthèse des causes et résolutions pertinentes")
    source_ids: list[str] = Field(default_factory=list, description="ticket_id cités")
