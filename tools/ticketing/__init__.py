"""Factory du backend de ticketing.

Usage:
    from tools.ticketing import get_ticketing_backend
    backend = get_ticketing_backend()
    backend.create_ticket(title=..., body=...)
"""
from __future__ import annotations

import logging
from typing import Any

from config.settings import get_settings
from tools.ticketing.base import TicketingBackend

logger = logging.getLogger(__name__)

_REGISTRY: dict[str, type[TicketingBackend]] = {}
_backend_instance: TicketingBackend | None = None


def register_backend(name: str, cls: type[TicketingBackend]) -> None:
    """Enregistre une implémentation de backend."""
    _REGISTRY[name.lower()] = cls


def get_ticketing_backend(
    backend_name: str | None = None,
    settings: Any | None = None,
) -> TicketingBackend:
    """Retourne l'instance configurée du backend de ticketing.

    Le backend est lu depuis la variable d'environnement TICKETING_BACKEND
    (valeurs supportées : zammad).
    """
    global _backend_instance

    settings = settings or get_settings()
    name = (backend_name or settings.TICKETING_BACKEND).lower()

    if _backend_instance is None or backend_name is not None:
        if name == "zammad":
            from tools.ticketing.zammad_backend import ZammadBackend

            _backend_instance = ZammadBackend()
        else:
            raise ValueError(f"Backend ticketing non supporté : {name}")

    return _backend_instance


def reset_backend() -> None:
    """Réinitialise le cache du backend (utile pour les tests)."""
    global _backend_instance
    _backend_instance = None
