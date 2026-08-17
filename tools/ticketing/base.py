"""Interface abstraite pour les backends de ticketing.

Aucun autre module du projet ne doit importer directement une implémentation
concrète (Zammad, ServiceNow, etc.) ; il doit passer par l'interface et la
factory définies ici.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TicketingBackend(ABC):
    """Contrat commun pour créer, chercher, lire et annoter des tickets."""

    @abstractmethod
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
        """Crée un ticket et retourne les métadonnées (id, state, etc.)."""
        ...

    @abstractmethod
    def search_tickets(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Recherche des tickets existants par texte libre."""
        ...

    @abstractmethod
    def add_note(
        self,
        ticket_id: str | int,
        body: str,
        internal: bool = True,
        **extra: Any,
    ) -> dict[str, Any]:
        """Ajoute une note/interne à un ticket existant."""
        ...

    @abstractmethod
    def get_ticket(self, ticket_id: str | int) -> dict[str, Any] | None:
        """Récupère un ticket par son identifiant backend."""
        ...

    @abstractmethod
    def push(self, ticket: dict[str, Any]) -> dict[str, Any]:
        """Formate et pousse un ticket au format CCU vers le backend.

        Cette méthode est un helper de haut niveau pour les agents du pipeline.
        """
        ...
