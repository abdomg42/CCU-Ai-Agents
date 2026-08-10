from typing import Optional
from pydantic import BaseModel, Field


class ContextSchema(BaseModel):
    """Contexte client consolidé."""

    customer_id: Optional[str] = Field(None, description="Identifiant client CRM")
    customer_name: Optional[str] = Field(None, description="Nom du client")
    segment: Optional[str] = Field(None, description="Segment client")
    subscription: Optional[dict] = Field(None, description="Abonnement lié au service")
    order: Optional[dict] = Field(None, description="Commande TMF622 liée")
    risk_factors: list[str] = Field(default_factory=list, description="Facteurs de risque identifiés")
    source_ids: list[str] = Field(default_factory=list, description="customer_id et order_id cités")
