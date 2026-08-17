"""Implémentation Zammad de l'interface TicketingBackend."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from config.settings import get_settings
from tools.ticketing.base import TicketingBackend

logger = logging.getLogger(__name__)


class ZammadBackend(TicketingBackend):
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

    def search_tickets(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Recherche de tickets existants par texte libre."""
        with self._client() as client:
            resp = client.get(
                "/api/v1/tickets/search",
                params={"query": query, "limit": limit},
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict):
                tickets = data.get("tickets", [])
            else:
                tickets = list(data)
            return tickets if isinstance(tickets, list) else []

    def create_ticket(
        self,
        title: str,
        body: str,
        customer: str | None = None,
        group: str | None = None,
        state: str | None = None,
        priority: str | None = None,
        tags: list[str] | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        """Crée un ticket Zammad."""
        payload = {
            "title": title,
            "group": group or self.default_group,
            "state": state or "new",
            "priority": priority or "2 normal",
            "customer": customer or "nicole.braun@zammad.org",
            "article": {
                "subject": title,
                "body": body,
                "type": "note",
                "internal": False,
            },
        }
        if tags:
            # Zammad attend une chaîne de tags séparés par des virgules, pas une liste.
            payload["tag"] = ", ".join(str(t) for t in tags)
        payload.update(extra)

        with self._client() as client:
            resp = client.post("/api/v1/tickets", json=payload)
            # Si le client n'existe pas encore, on le crée automatiquement puis on réessaie.
            if resp.status_code == 422 and "No lookup value found for 'customer'" in resp.text:
                logger.warning("Client Zammad inconnu (%s), création automatique...", customer)
                try:
                    self._ensure_customer(client, str(customer))
                    resp = client.post("/api/v1/tickets", json=payload)
                except Exception as exc:
                    logger.warning(
                        "Impossible de créer le client %s (%s); le ticket reste en échec.",
                        customer,
                        exc,
                    )
            if resp.status_code >= 400:
                logger.error(
                    "Zammad ticket creation failed (%s): %s - %s",
                    resp.status_code,
                    resp.text,
                    payload,
                )
            resp.raise_for_status()
            return resp.json()

    def _ensure_customer(self, client: httpx.Client, email: str) -> dict[str, Any]:
        """Crée un utilisateur Zammad minimal s'il n'existe pas déjà."""
        login = (email.split("@")[0] if "@" in email else email).lower()
        user_payload = {
            "login": login,
            "email": email.lower(),
            "firstname": "Client",
            "lastname": login,
        }
        resp = client.post("/api/v1/users", json=user_payload)
        resp.raise_for_status()
        return resp.json()

    def add_note(
        self,
        ticket_id: str | int,
        body: str,
        internal: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        """Ajoute une note interne à un ticket."""
        payload = {
            "ticket_id": ticket_id,
            "subject": extra.get("subject", "Diagnostic agent note"),
            "body": body,
            "type": "note",
            "internal": internal,
        }
        payload.update({k: v for k, v in extra.items() if k != "subject"})

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

    def push(self, ticket: dict[str, Any]) -> dict[str, Any]:
        """Pousse un ticket au format CCU vers Zammad et retourne le résultat.

        Format attendu : ticket_id, short_description, description, priority,
        category, status, root_cause, resolution_notes, client_id, product_type.
        """
        # Les priorités par défaut dans Zammad sont "1 low", "2 normal", "3 high".
        priority_map = {
            "P1": "3 high",
            "P2": "2 normal",
            "P3": "1 low",
            "P4": "1 low",
        }
        zammad_priority = priority_map.get(str(ticket.get("priority", "")).upper(), "2 normal")

        state_map = {
            "new": "new",
            "open": "open",
            "closed": "closed",
            "resolved": "closed",
            "pending": "pending reminder",
        }
        raw_state = str(ticket.get("status", "new")).lower()
        zammad_state = state_map.get(raw_state, "new")

        body = ticket.get("description") or ticket.get("short_description") or "No description"
        if ticket.get("root_cause"):
            body += f"\n\nRoot cause: {ticket['root_cause']}"
        if ticket.get("resolution_notes"):
            body += f"\n\nResolution notes: {ticket['resolution_notes']}"

        tags = [ticket.get("category", "ccu")]
        if ticket.get("product_type"):
            tags.append(ticket["product_type"])

        title = ticket.get("short_description") or f"CCU incident {ticket.get('ticket_id')}"

        customer = ticket.get("client_id") or "nicole.braun@zammad.org"
        if "@" not in customer:
            customer = f"{customer}@ccu.local"

        result = self.create_ticket(
            title=title,
            body=body,
            customer=customer,
            priority=zammad_priority,
            tags=tags,
            state=zammad_state,
        )
        logger.info("Ticket Zammad créé : %s", result.get("id"))
        return result
