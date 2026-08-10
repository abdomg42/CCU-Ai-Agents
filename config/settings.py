import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")


class Settings:
    """Configuration centralisée du projet diagnostic-technique."""

    PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

    # LLM configuration
    # Ollama est le moteur local par défaut. Décommenter/adapter la section
    # Anthropic ci-dessous pour switcher vers Claude (nécessite ANTHROPIC_API_KEY).
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5")

    # Pour tests et démo sans Ollama disponible
    MOCK_LLM: bool = os.getenv("MOCK_LLM", "false").lower() in {"1", "true", "yes"}

    # ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    # ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20240620")

    # Vector store (ChromaDB embarqué)
    CHROMA_PERSIST_DIR: Path = PROJECT_ROOT / "data" / "chroma"
    TICKETS_COLLECTION: str = os.getenv("TICKETS_COLLECTION", "ccu_tickets")
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Mocks
    MOCKS_DIR: Path = PROJECT_ROOT / "mocks"
    MOCK_LOGS: Path = MOCKS_DIR / "mock_logs.json"
    MOCK_CRM: Path = MOCKS_DIR / "mock_crm.json"
    MOCK_ORDERS: Path = MOCKS_DIR / "mock_orders_tmf622.json"
    MOCK_TICKETS_DIR: Path = MOCKS_DIR / "mock_tickets"

    # Guardrail
    WHITELIST_PATH: Path = (
        PROJECT_ROOT
        / "sub_agents"
        / "guardrail_validator"
        / "action_whitelist.yaml"
    )

    # Audit
    AUDIT_LOG_PATH: Path = PROJECT_ROOT / "data" / "audit.log"


def get_settings() -> Settings:
    return Settings()
