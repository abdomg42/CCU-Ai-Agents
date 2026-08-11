"""API FastAPI du diagnostic technique CCU.

Endpoint :
    POST /diagnose -> exécute le pipeline LangGraph complet et retourne l'état final.
"""
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
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


def _format_diagnostic(result: dict[str, Any]) -> str:
    """Formatte le diagnostic JSON en un résumé lisible dans un terminal/curl."""
    incident = result.get("incident") or {}
    parsed = result.get("parsed_incident") or {}
    logs = result.get("logs") or {}
    context = result.get("customer_context") or {}
    similar = result.get("similar_tickets") or {}
    root = result.get("root_cause") or {}
    remediation = result.get("remediation") or {}

    lines: list[str] = [
        "=== DIAGNOSTIC CCU ===",
        "",
        f"Incident : {incident.get('title', 'N/A')}",
        f"Priorité : {incident.get('priority', 'N/A')}",
        f"Source   : {incident.get('source', 'N/A')}",
        "",
        # "-- Résumé --",
        # f"{parsed.get('summary', 'Non disponible')}",
        # "",
        # "-- Produits / Services impactés --",
    ]

    products = parsed.get("products") or []
    services = parsed.get("services") or []
    if products or services:
        for p in products:
            lines.append(f"  Produit : {p}")
        for s in services:
            lines.append(f"  Service : {s}")
    else:
        lines.append("  Aucun produit/service identifié")

    lines.extend(["", "-- Logs --"]) #f"  Statut : {logs.get('status', 'N/A')}"])
    log_summary = logs.get("summary") or logs.get("log_summary") or "Aucun log analysé"
    lines.append(f"  Résumé : {log_summary}")

    # lines.extend(["", "-- Contexte client --", f"  Statut : {context.get('status', 'N/A')}"])
    # ctx_summary = context.get("summary") or context.get("context_summary") or "Aucun contexte client"
    # lines.append(f"  Résumé : {ctx_summary}")

    # lines.extend(["", "-- Tickets similaires --", f"  Statut : {similar.get('status', 'N/A')}"])
    # tickets = similar.get("tickets") or []
    # if tickets:
    #     for t in tickets[:3]:
    #         lines.append(f"  - {t.get('id', 'N/A')}: {t.get('summary', 'N/A')} (score {t.get('score', 'N/A')})")
    # else:
    #     lines.append("  Aucun ticket similaire trouvé")

    lines.extend([
        "",
        "-- Cause racine --",
        f"  Cause      : {root.get('cause', 'N/A')}",
        f"  Confiance  : {root.get('confidence', 'N/A')}",
        f"  Explication: {root.get('explanation', 'N/A')}",
        "",
        # "-- Action proposée --",
        # f"  Action : {remediation.get('action', 'N/A')}",
        # f"  Étapes : {remediation.get('steps', 'N/A')}",
        "",
        "-- Risque & Validation --",
        f"  Niveau de risque    : {result.get('risk_level', 'N/A')}",
        f"  Statut de validation : {result.get('validation_status', 'N/A')}",
        f"  Motif               : {result.get('validation_reason', 'N/A')}",
        "",
        "======================",
    ])

    if result.get("error"):
        lines.extend(["", f"ERREUR : {result['error']}"])

    return "\n".join(lines)


@app.post("/diagnose", response_model=DiagnosticOutput)
def diagnose(incident: IncidentInput) -> dict[str, Any]:
    """Exécute le pipeline de diagnostic sur un incident brut."""
    payload = incident.model_dump()
    result = run_diagnosis(payload)
    return result


@app.post("/diagnose/text", response_class=PlainTextResponse)
def diagnose_text(incident: IncidentInput) -> str:
    """Exécute le pipeline et retourne un résumé textuel simple à lire dans curl."""
    payload = incident.model_dump()
    result = run_diagnosis(payload)
    return _format_diagnostic(result)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
