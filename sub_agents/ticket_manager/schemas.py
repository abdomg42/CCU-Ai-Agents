from pydantic import BaseModel, Field


class TicketMappingResult(BaseModel):
    """Résultat du mapping d'un incident sur un ticket existant ou nouveau."""

    status: str = Field(
        ...,
        description="linked_to_existing ou created_new",
    )
    ticket_id: str = Field(..., description="Identifiant du ticket lié ou créé")
    similarity_score: float = Field(
        default=0.0,
        description="Score de similarité cosine (0 si nouveau ticket)",
    )
