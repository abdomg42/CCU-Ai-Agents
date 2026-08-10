from pydantic import BaseModel, Field


class ProposedAction(BaseModel):
    """Action corrective proposée, non exécutée."""

    action: str = Field(..., description="Description de l'action proposée")
    justification: str = Field(..., description="Justification liée à la cause racine")
    source_ids: list[str] = Field(default_factory=list, description="Sources justifiant l'action")


class RemediationSchema(BaseModel):
    """Plan de remédiation proposé."""

    actions: list[ProposedAction] = Field(default_factory=list, description="Actions proposées")
    note_execution: str = Field(
        default="Aucune action n'a été exécutée automatiquement. Validation humaine requise.",
        description="Rappel que les actions restent proposées",
    )
