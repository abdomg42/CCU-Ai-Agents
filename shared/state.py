"""État partagé du graphe LangGraph.

On utilise un Pydantic model pour bénéficier de la validation native et d'une
représentation JSON claire dans les réponses API.
"""
from typing import Any, Optional
from pydantic import BaseModel, Field


class ParsedIncident(BaseModel):
    service_id: Optional[str] = None
    order_id: Optional[str] = None
    customer_id: Optional[str] = None
    incident_type: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None


class GraphState(BaseModel):
    """État partagé entre les nœuds du graphe."""

    incident: dict[str, Any] = Field(default_factory=dict)
    parsed_incident: dict[str, Any] = Field(default_factory=dict)

    # Résultats des agents collecteurs
    logs: Optional[dict[str, Any]] = None
    customer_context: Optional[dict[str, Any]] = None
    similar_tickets: Optional[dict[str, Any]] = None

    # Résultats des agents raisonneurs
    root_cause: Optional[dict[str, Any]] = None
    remediation: Optional[dict[str, Any]] = None

    # Guardrail
    risk_level: Optional[str] = None  # Faible / Moyen / Critique
    validation_status: Optional[str] = None  # approuvée_conditionnelle / refusée
    validation_reason: Optional[str] = None

    # Debug / observabilité
    traces: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

    def add_trace(self, node: str, detail: dict[str, Any]) -> None:
        self.traces.append({"node": node, "detail": detail})
