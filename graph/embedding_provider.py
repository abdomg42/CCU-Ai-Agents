"""Interface abstraite pour les modèles d'embedding.

Permet de brancher :
- Ollama (défaut : mxbai-embed-large:latest)
- sentence-transformers (local, offline)
- OpenAI Embeddings
- Voyage AI Embeddings
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from config.settings import Settings, get_settings


class EmbeddingProvider(ABC):
    """Contrat minimal : embed(liste de textes) -> liste de vecteurs."""

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Retourne un vecteur par texte fourni."""
        ...


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Provider Ollama local via l'endpoint /api/embeddings."""

    def __init__(
        self,
        model_name: str | None = None,
        base_url: str | None = None,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError(
                "httpx est requis pour le provider Ollama. "
                "Installez-le avec : pip install httpx"
            ) from exc
        self._httpx = httpx
        settings = get_settings()
        self.model_name = model_name or settings.EMBEDDING_MODEL
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    def embed(self, texts: list[str]) -> list[list[float]]:
        url = f"{self.base_url}/api/embeddings"
        embeddings: list[list[float]] = []
        for text in texts:
            response = self._httpx.post(
                url,
                json={"model": self.model_name, "prompt": text},
                timeout=120.0,
            )
            response.raise_for_status()
            data = response.json()
            embeddings.append(data["embedding"])
        return embeddings


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    """Provider offline basé sur sentence-transformers."""

    def __init__(self, model_name: str | None = None) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise ImportError(
                "sentence-transformers est requis pour ce provider. "
                "Installez-le avec : pip install sentence-transformers"
            ) from exc
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self._model: Any = None

    def _load(self) -> Any:
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        model = self._load()
        vectors = model.encode(texts, show_progress_bar=False)
        return [v.tolist() for v in vectors]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Provider OpenAI (à brancher avec OPENAI_API_KEY)."""

    def __init__(self, model_name: str = "text-embedding-3-small", api_key: str | None = None) -> None:
        self.model_name = model_name
        self.api_key = api_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("OpenAI embeddings non encore branché.")


class VoyageAIEmbeddingProvider(EmbeddingProvider):
    """Provider Voyage AI (à brancher avec VOYAGE_API_KEY)."""

    def __init__(self, model_name: str = "voyage-2", api_key: str | None = None) -> None:
        self.model_name = model_name
        self.api_key = api_key

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError("Voyage AI embeddings non encore branché.")


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    """Factory : retourne le provider d'embedding configuré."""
    s = settings or get_settings()
    provider = s.EMBEDDING_PROVIDER.lower().strip()
    if provider == "openai":
        return OpenAIEmbeddingProvider(model_name=s.EMBEDDING_MODEL)
    if provider in {"voyage", "voyageai"}:
        return VoyageAIEmbeddingProvider(model_name=s.EMBEDDING_MODEL)
    if provider in {"ollama"}:
        return OllamaEmbeddingProvider(model_name=s.EMBEDDING_MODEL)
    return SentenceTransformerEmbeddingProvider(model_name=s.EMBEDDING_MODEL)
