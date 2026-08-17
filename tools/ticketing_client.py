"""Facade rétrocompatible vers le backend de ticketing configuré.

Les appelants existants peuvent toujours importer `ZammadClient` ou
`push_ticket_to_zammad` depuis ce module, mais ceux-ci sont désormais des
wrappers autour de la factory abstraite.

Pour tout nouveau code, préférer :
    from tools.ticketing import get_ticketing_backend
    backend = get_ticketing_backend()
"""
from __future__ import annotations

import logging
from typing import Any

from tools.ticketing import get_ticketing_backend
from tools.ticketing.base import TicketingBackend

logger = logging.getLogger(__name__)


# Alias rétrocompatible vers l'implémentation Zammad actuellement configurée.
class ZammadClient:
    """Wrapper rétrocompatible vers le backend Zammad configuré."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._backend = get_ticketing_backend()

    def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        return self._backend.search_tickets(query, limit)

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
        return self._backend.create_ticket(
            title=title,
            body=body,
            customer=customer,
            group=group,
            state=state,
            priority=priority,
            tags=tags,
        )

    def add_note(self, ticket_id: str | int, body: str, internal: bool = True) -> dict[str, Any]:
        return self._backend.add_note(ticket_id, body, internal=internal)

    def get_ticket(self, ticket_id: str | int) -> dict[str, Any] | None:
        return self._backend.get_ticket(ticket_id)


def push_ticket_to_zammad(ticket: dict[str, Any]) -> dict[str, Any]:
    """Pousse un ticket au format CCU vers le backend configuré."""
    backend = get_ticketing_backend()
    return backend.push(ticket)


__all__ = ["ZammadClient", "push_ticket_to_zammad", "TicketingBackend", "get_ticketing_backend"]
