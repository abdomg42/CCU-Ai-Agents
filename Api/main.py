"""API FastAPI du diagnostic technique CCU.

Endpoint :
    POST /diagnose -> exécute le pipeline LangGraph complet et retourne l'état final.
"""
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from orchestrator.pipeline import run_diagnosis

app = FastAPI(
    title="Diagnostic Technique CCU",
    description="Agent IA de diagnostic technique pour CCU (TMF620/TMF622).",
    version="0.1.0",
)


class IncidentInput(BaseModel):
    """Incident brut envoyé par le NOC / le client / un autre système."""

    title: str
    description: str
    source: str = "api"
    priority: str = "P3"
    metadata: dict[str, Any] = {}


class DiagnosticOutput(BaseModel):
    """Diagnostic structuré complet avec toutes les étapes intermédiaires."""

    incident: dict[str, Any]
    parsed_incident: dict[str, Any]
    logs: dict[str, Any] | None
    customer_context: dict[str, Any] | None
    similar_tickets: dict[str, Any] | None
    root_cause: dict[str, Any] | None
    remediation: dict[str, Any] | None
    risk_level: str | None
    validation_status: str | None
    validation_reason: str | None
    traces: list[dict[str, Any]] = []
    error: str | None = None


@app.post("/diagnose", response_model=DiagnosticOutput)
def diagnose(incident: IncidentInput) -> dict[str, Any]:
    """Exécute le pipeline de diagnostic sur un incident brut."""
    payload = incident.model_dump()
    result = run_diagnosis(payload)
    return result


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
