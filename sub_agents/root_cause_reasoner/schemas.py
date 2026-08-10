from pydantic import BaseModel, Field


class RootCauseSchema(BaseModel):
    """Diagnostic de cause racine."""

    confidence: str = Field(..., description="forte, moyenne ou faible")
    cause: str = Field(..., description="Cause racine en français, ou 'indéterminée'")
    explanation: str = Field(..., description="Explication courte justifiée par les sources")
    source_ids: list[str] = Field(default_factory=list, description="log_id, ticket_id, order_id cités")
