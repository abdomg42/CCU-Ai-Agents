from typing import Optional
from pydantic import BaseModel, Field, field_validator


class IncidentSchema(BaseModel):
    """Incident normalisé par l'agent d'intake."""

    service_id: Optional[str] = Field(None, description="Identifiant du service impacté")
    order_id: Optional[str] = Field(None, description="Identifiant de la commande TMF622 liée")
    customer_id: Optional[str] = Field(None, description="Identifiant du client CRM")

    @field_validator("service_id", "order_id", "customer_id", mode="before")
    @classmethod
    def _stringify_ids(cls, value):
        """Les systèmes externes (Zammad, Splunk, etc.) peuvent envoyer des IDs numériques."""
        return str(value) if value is not None else None
    incident_type: Optional[str] = Field(None, description="Type d'incident (ex: fibre, mobile, lan, sim, billing)")
    description: Optional[str] = Field(None, description="Description synthétique de l'incident")
    priority: Optional[str] = Field(None, description="Priorité déduite : P1, P2, P3 ou P4")
