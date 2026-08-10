"""Client LLM unifié.

Ollama est utilisé par défaut en local. Le mode MOCK_LLM permet d'exécuter le
pipeline sans modèle téléchargé, en retournant des réponses déterministes
utiles pour les tests et les démonstrations.

Pour basculer vers Anthropic Claude, remplacer l'import/instanciation ci-dessous
par ChatAnthropic et décommenter les variables dans config/settings.py.
"""
import json
from typing import Any, Type, TypeVar

from pydantic import BaseModel
from langchain_ollama import ChatOllama

from config.settings import get_settings

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def _mock_invoke(
        self, system: str, user: str, response_model: Type[T]
    ) -> T:
        """Réponse déterministe quand MOCK_LLM est activé."""
        # On renvoie un dictionnaire vide-ish qui respecte la structure Pydantic.
        # Les agents implémentent ensuite des fallbacks logiques sur ce résultat.
        return response_model()

    def invoke_structured(
        self, system: str, user: str, response_model: Type[T]
    ) -> T:
        if self.settings.MOCK_LLM:
            return self._mock_invoke(system, user, response_model)

        llm = ChatOllama(
            base_url=self.settings.OLLAMA_BASE_URL,
            model=self.settings.OLLAMA_MODEL,
            temperature=0.0,
            format="json",
        )
        structured = llm.with_structured_output(
            response_model, method="json_mode", include_raw=False
        )
        messages = [
            ("system", system),
            ("human", user),
        ]
        return structured.invoke(messages)  # type: ignore[return-value]

    def invoke_text(self, system: str, user: str) -> str:
        if self.settings.MOCK_LLM:
            return "{}"

        llm = ChatOllama(
            base_url=self.settings.OLLAMA_BASE_URL,
            model=self.settings.OLLAMA_MODEL,
            temperature=0.0,
        )
        messages = [("system", system), ("human", user)]
        return str(llm.invoke(messages).content)
