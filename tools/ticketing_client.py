"""Client bas niveau pour l'API Zammad (Ticketing).

Toutes les méthodes sont des opérations d'information/écriture de tickets
(pas d'action technique exécutée).
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from config.settings import get_settings

logger = logging.getLogger(__name__)


class ZammadClient:
    """Wrapper autour de l'API REST Zammad."""

    def __init__(
        self,
        base_url: str | None = None,
        token: str | None = None,
        default_group: str | None = None,
    ) -> None:
        settings = get_settings()
        self.base_url = (base_url or settings.ZAMMAD_URL).rstrip("/")
        self.token = token or settings.ZAMMAD_TOKEN
        self.default_group = default_group or settings.ZAMMAD_DEFAULT_GROUP

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise RuntimeError("ZAMMAD_TOKEN non configuré")
        return {
            "Authorization": f"Token token={self.token}",
            "Content-Type": "application/json",
        }

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, headers=self._headers(), timeout=30.0)

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Recherche de tickets existants par texte libre."""
        with self._client() as client:
            resp = client.get(
                "/api/v1/tickets/search",
                params={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            # Zammad retourne parfois { "assets": ..., "tickets": [...] }
            if isinstance(data, dict):
                tickets = data.get("tickets", [])
            else:
                tickets = list(data)
            return tickets if isinstance(tickets, list) else []

    def create_ticket(
        self,
        title: str,
        body: str,
        customer: str = "nicole.braun@zammad.org",
        group: str | None = None,
        state: str = "new",
        priority: str = "2 normal",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Crée un ticket Zammad (information seulement, pas d'action technique)."""
        payload = {
            "title": title,
            "group": group or self.default_group,
            "state": state,
            "priority": priority,
            "customer": customer,
            "article": {
                "subject": title,
                "body": body,
                "type": "note",
                "internal": False,
            },
        }
        if tags:
            payload["tags"] = tags

        with self._client() as client:
            resp = client.post("/api/v1/tickets", json=payload)
            resp.raise_for_status()
            return resp.json()

    def add_note(self, ticket_id: str | int, body: str, internal: bool = True) -> dict[str, Any]:
        """Ajoute une note interne à un ticket (information seulement)."""
        payload = {
            "ticket_id": ticket_id,
            "subject": "Diagnostic agent note",
            "body": body,
            "type": "note",
            "internal": internal,
        }
        with self._client() as client:
            resp = client.post("/api/v1/ticket_articles", json=payload)
            resp.raise_for_status()
            return resp.json()

    def get_ticket(self, ticket_id: str | int) -> dict[str, Any] | None:
        """Récupère un ticket par son ID."""
        with self._client() as client:
            resp = client.get(f"/api/v1/tickets/{ticket_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json()


def push_ticket_to_zammad(ticket: dict[str, Any]) -> dict[str, Any]:
    """Pousse un ticket au format CCU vers Zammad et retourne le résultat.

    Le format attendu en entrée : ticket_id, short_description, description,
    priority, category, status, root_cause, resolution_notes, client_id, etc.
    """
    client = ZammadClient()

    # Mapping heuristique priorité
    priority_map = {
        "P1": "1 critical",
        "P2": "2 high",
        "P3": "3 normal",
        "P4": "4 low",
    }
    zammad_priority = priority_map.get(str(ticket.get("priority", "")).upper(), "2 normal")

    body = ticket.get("description") or ticket.get("short_description") or "No description"
    if ticket.get("root_cause"):
        body += f"\n\nRoot cause: {ticket['root_cause']}"
    if ticket.get("resolution_notes"):
        body += f"\n\nResolution notes: {ticket['resolution_notes']}"

    tags = [ticket.get("category", "ccu")]
    if ticket.get("product_type"):
        tags.append(ticket["product_type"])

    title = ticket.get("short_description") or f"CCU incident {ticket.get('ticket_id')}"

    result = client.create_ticket(
        title=title,
        body=body,
        customer=ticket.get("client_id", "nicole.braun@zammad.org"),
        priority=zammad_priority,
        tags=tags,
        state=ticket.get("status", "new"),
    )
    logger.info("Ticket Zammad créé : %s", result.get("id"))
    return result
