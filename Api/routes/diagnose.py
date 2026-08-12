"""Route SSE /diagnose : accepte du texte libre et streame la progression.

Chaque événement correspond à un nœud traversé par le graphe LangGraph.
Le dernier événement contient l'état final complet.
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from orchestrator.pipeline import stream_diagnosis

router = APIRouter()


class DiagnoseTextInput(BaseModel):
    """Texte libre décrivant l'incident."""

    text: str


def _node_summary(node: str, update: dict[str, Any]) -> dict[str, Any]:
    """Résume le résultat d'un nœud pour le stream SSE."""
    if node == "intake":
        parsed = update.get("parsed_incident", {})
        return {
            "node": node,
            "summary": (
                f"Incident parsed: type={parsed.get('incident_type')}, "
                f"customer={parsed.get('customer_id')}, service={parsed.get('service_id')}, "
                f"order={parsed.get('order_id')}"
            ),
        }
    if node == "collectors":
        parts = []
        if update.get("logs"):
            parts.append("logs")
        if update.get("customer_context"):
            parts.append("context")
        if update.get("similar_tickets"):
            parts.append("similar tickets")
        return {"node": node, "summary": f"Collected sources: {', '.join(parts) or 'none'}"}
    if node == "root_cause":
        root = update.get("root_cause", {})
        return {
            "node": node,
            "summary": f"Root cause: {root.get('cause')} (confidence={root.get('confidence')})",
        }
    if node == "ticket_manager":
        mapping = update.get("ticket_mapping", {})
        return {
            "node": node,
            "summary": (
                f"Ticket {mapping.get('status')}: {mapping.get('ticket_id')} "
                f"(score={mapping.get('similarity_score')})"
            ),
        }
    if node == "remediation_explainer":
        explanation = update.get("remediation_explanation", "")
        first_line = explanation.split("\n")[0] if explanation else "Explanation generated"
        return {"node": node, "summary": first_line}
    if node == "content_guardrail":
        return {
            "node": node,
            "summary": "PII check completed before report generation",
        }
    if node == "report_generator":
        return {
            "node": node,
            "summary": f"Report generated: {update.get('report_path')}",
        }
    if node == "notifier":
        sent = update.get("email_sent", False)
        return {
            "node": node,
            "summary": f"Email notification: {'sent' if sent else 'failed'}",
        }
    return {"node": node, "summary": "Node completed"}


def _sse_event(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/stream")
def diagnose_sse(input_data: DiagnoseTextInput) -> StreamingResponse:
    """Streame un événement par nœud du graphe traversé."""
    incident = {
        "title": "Chat incident",
        "description": input_data.text,
        "source": "chat",
        "priority": "P3",
    }

    def event_generator():
        final_state: dict[str, Any] = {}
        for chunk in stream_diagnosis(incident):
            # chunk is a dict with a single node key
            for node, update in chunk.items():
                final_state.update(update)
                yield _sse_event(_node_summary(node, update))

        final_state.update(incident=incident)
        yield _sse_event({"node": "final", "summary": "Diagnostic complete", "result": final_state})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
