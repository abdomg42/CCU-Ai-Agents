from pydantic import BaseModel, Field


class GuardrailSchema(BaseModel):
    """Résultat de la validation guardrail."""

    validation_status: str = Field(
        ...,
        description="approuvée_conditionnelle ou refusée",
    )
    risk_level: str = Field(
        ...,
        description="Faible, Moyen ou Critique",
    )
    reason: str = Field(..., description="Explication de la décision")
    allowed_actions: list[str] = Field(default_factory=list, description="Actions autorisées")
    rejected_actions: list[str] = Field(default_factory=list, description="Actions rejetées")
