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
    remediation_explanation: Optional[str] = None

    # Ticket mapping / création
    ticket_mapping: Optional[dict[str, Any]] = None

    # Guardrail de contenu (PII)
    sanitized_what_happened: Optional[str] = None
    sanitized_root_cause: Optional[str] = None
    sanitized_root_cause_explanation: Optional[str] = None
    sanitized_recommendation: Optional[str] = None

    # Génération de rapport et notification
    report_path: Optional[str] = None
    email_sent: bool = False
    email_recipients: list[str] = Field(default_factory=list)
    zammad_note_added: bool = False

    # Debug / observabilité
    traces: list[dict[str, Any]] = Field(default_factory=list)
    error: Optional[str] = None

    def add_trace(self, node: str, detail: dict[str, Any]) -> None:
        self.traces.append({"node": node, "detail": detail})
