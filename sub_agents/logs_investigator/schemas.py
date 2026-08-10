from typing import Optional
from pydantic import BaseModel, Field


class LogInvestigationSchema(BaseModel):
    """Résultat de l'investigation de logs."""

    relevant_logs: list[dict] = Field(default_factory=list, description="Logs pertinents")
    summary: str = Field(..., description="Synthèse en français de la situation technique")
    source_ids: list[str] = Field(default_factory=list, description="log_id cités")
    has_clear_signal: bool = Field(False, description="True si un signal technique clair est présent")
