"""API FastAPI du diagnostic technique CCU.

Endpoints :
    POST /diagnose -> exécute le pipeline LangGraph complet et retourne l'état final.
    POST /diagnose/text -> résumé textuel simple.
    GET /health -> healthcheck.
"""
from typing import Any

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from orchestrator.pipeline import run_diagnosis
from api.routes import diagnose as diagnose_router

app = FastAPI(
    title="Diagnostic Technique CCU",
    description="Agent IA de diagnostic technique pour CCU (TMF620/TMF622). "
                "Aucune action technique n'est exécutée automatiquement.",
    version="0.2.0",
)

app.include_router(diagnose_router.router, prefix="/diagnose")


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
    remediation_explanation: str | None
    ticket_mapping: dict[str, Any] | None
    sanitized_what_happened: str | None
    sanitized_root_cause: str | None
    sanitized_recommendation: str | None
    report_path: str | None
    email_sent: bool
    email_recipients: list[str] = []
    zammad_note_added: bool
    traces: list[dict[str, Any]] = []
    error: str | None = None


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


@app.get("/reports/{report_id}")
def download_report(report_id: str) -> Any:
    """Sert le fichier PDF/HTML du rapport généré."""
    from fastapi.responses import FileResponse

    settings = get_settings()
    for ext in (".pdf", ".html"):
        path = settings.REPORTS_DIR / f"{report_id}{ext}"
        if path.exists():
            return FileResponse(
                path,
                filename=path.name,
                media_type="application/pdf" if ext == ".pdf" else "text/html",
            )
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Report not found")


def _format_diagnostic(result: dict[str, Any]) -> str:
    """Formatte le diagnostic JSON en un résumé lisible dans un terminal/curl."""
    incident = result.get("incident") or {}
    parsed = result.get("parsed_incident") or {}
    root = result.get("root_cause") or {}
    mapping = result.get("ticket_mapping") or {}

    lines: list[str] = [
        "=== DIAGNOSTIC CCU ===",
        "",
        f"Incident : {incident.get('title', 'N/A')}",
        f"Priorité : {incident.get('priority', 'N/A')}",
        f"Source   : {incident.get('source', 'N/A')}",
        "",
        "-- Contexte --",
        f"  Client   : {parsed.get('customer_id', 'N/A')}",
        f"  Commande : {parsed.get('order_id', 'N/A')}",
        f"  Service  : {parsed.get('service_id', 'N/A')}",
        f"  Type     : {parsed.get('incident_type', 'N/A')}",
        "",
        "-- Cause racine --",
        f"  Cause      : {root.get('cause', 'N/A')}",
        f"  Confiance  : {root.get('confidence', 'N/A')}",
        f"  Explication: {root.get('explanation', 'N/A')}",
        "",
        "-- Mapping ticket --",
        f"  Statut : {mapping.get('status', 'N/A')}",
        f"  Ticket : {mapping.get('ticket_id', 'N/A')}",
        f"  Score  : {mapping.get('similarity_score', 'N/A')}",
        "",
        "-- Recommandation --",
        f"  {result.get('remediation_explanation', 'N/A')}",
        "",
        "-- Livrables --",
        f"  Rapport  : {result.get('report_path', 'N/A')}",
        f"  Email    : {'envoyé' if result.get('email_sent') else 'non envoyé'}",
        "",
        "======================",
    ]

    if result.get("error"):
        lines.extend(["", f"ERREUR : {result['error']}"])

    return "\n".join(lines)
