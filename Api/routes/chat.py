"""Route /chat : réponses conversationnelles générales.

Ce endpoint ne déclenche pas le pipeline de diagnostic. Il est utilisé par
le mode Chat de l'interface Streamlit pour les questions libres.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from sub_agents.chat_agent.agent import run_chat

router = APIRouter()


class ChatInput(BaseModel):
    """Message utilisateur et historique optionnel."""

    message: str
    history: list[dict[str, str]] = []


class ChatOutput(BaseModel):
    """Réponse conversationnelle de l'agent."""

    chat_response: str


@router.post("/")
def chat(input_data: ChatInput) -> dict[str, Any]:
    """Répond à une question libre en mode conversation."""
    result = run_chat(input_data.message, history=input_data.history)
    return result
