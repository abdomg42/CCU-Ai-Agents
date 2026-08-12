"""Guardrail de contenu : détection et remplacement des PII.

L'agent scanne les valeurs textuelles du dictionnaire d'état avant génération
 du rapport. Il remplace les noms complets, emails, téléphones et adresses
 par les identifiants techniques déjà présents (client_id, order_id, etc.).

Aucun envoi externe n'est effectué ici : c'est une passe de nettoyage locale.
"""
from __future__ import annotations

import re
from typing import Any

from shared.state import GraphState


# Patterns simples et conservateurs pour la détection PII.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{2,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}")
_IP_ADDRESS_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_STREET_KEYWORDS_RE = re.compile(
    r"\b\d+\s+(?:rue|avenue|boulevard|route|chemin|place|impasse|allée|bd|av|route)\s+[^,\n]{5,}",
    re.IGNORECASE,
)
# Noms propres complets : deux mots commençant par une majuscule, sans chiffres.
_FULL_NAME_RE = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\b")


def _replace_in_text(text: str, replacements: dict[re.Pattern[str], str]) -> str:
    if not text or not isinstance(text, str):
        return text
    for pattern, replacement in replacements.items():
        text = pattern.sub(replacement, text)
    return text


def _build_replacements(state: GraphState) -> dict[re.Pattern[str], str]:
    parsed = state.parsed_incident or {}
    incident = state.incident or {}
    client_id = parsed.get("customer_id") or incident.get("customer_id") or "CLIENT_ID"
    order_id = parsed.get("order_id") or incident.get("order_id") or "ORDER_ID"
    service_id = parsed.get("service_id") or incident.get("service_id") or "SERVICE_ID"

    return {
        _EMAIL_RE: "[EMAIL_REDACTED]",
        _PHONE_RE: f"[PHONE_REDACTED -> contact {client_id}]",
        _IP_ADDRESS_RE: "[IP_REDACTED]",
        _STREET_KEYWORDS_RE: "[ADDRESS_REDACTED]",
        # Remplacement des noms propres complets par le client_id technique.
        _FULL_NAME_RE: client_id,
    }


def sanitize_state_texts(state: GraphState) -> dict[str, Any]:
    """Nettoie les champs textuels sensibles de l'état et retourne les versions nettoyées.

    Retourne un dictionnaire {what_happened, root_cause, recommendation}
    prêt à être consommé par le générateur de rapport.
    """
    replacements = _build_replacements(state)

    root_cause = state.root_cause or {}
    remediation_explanation = state.remediation_explanation or ""

    what_happened = state.incident.get("description", "") if state.incident else ""
    root_cause_text = root_cause.get("cause", "")
    root_cause_explanation = root_cause.get("explanation", "")
    recommendation = remediation_explanation

    return {
        "what_happened": _replace_in_text(what_happened, replacements),
        "root_cause": _replace_in_text(root_cause_text, replacements),
        "root_cause_explanation": _replace_in_text(root_cause_explanation, replacements),
        "recommendation": _replace_in_text(recommendation, replacements),
    }


def run_content_guardrail(state: GraphState) -> dict[str, Any]:
    """Point d'entrée LangGraph pour le guardrail de contenu."""
    sanitized = sanitize_state_texts(state)
    return {
        "sanitized_what_happened": sanitized["what_happened"],
        "sanitized_root_cause": sanitized["root_cause"],
        "sanitized_root_cause_explanation": sanitized["root_cause_explanation"],
        "sanitized_recommendation": sanitized["recommendation"],
    }
